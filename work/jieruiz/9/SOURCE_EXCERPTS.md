# Source evidence for current routing and local later versions

Local v5/v6 excerpts are evidence only, not a complete runtime publication.

## attention_tlm_v3.py:197-227

```python
def summary(self,t,L,layer):
    b=math.ceil(L/64);size=self.kheads*b*4*self.dim*4
    name=f'L{layer}/summary'
    if layer not in self.summary_built:
        if self.ac['summary_initialization']=='cold_build':
            for start in range(0,L,self.ac['kv_tile_tokens']):
                ids=range(start,min(L,start+self.ac['kv_tile_tokens']))
                reads=[(self.kv_address(layer,i,k),self.vecbytes) for i in ids for k in range(self.kheads)]
                t=self.ranges(t,reads,'summary_build_K')
                n=len(reads)*self.dim
                t=self.scratch(t,write=n*2,kind='summary_input');t=self.scratch(t,read=n*2,kind='summary_input')
                t=self.op(t,'summary_build',vec=n)
            addr=self.ext.layout.address(name,0,size);start=t
            t=self.ext.access(t,size,'ATT_summary',True,address=addr)
            self.record('DRAM_summary_initial_write',start,t,address=addr,bytes=size,resource='external_memory')
        self.summary_built.add(layer)
    else:
        # Sub-summary sums are laid out [block, sub, KV head, dim].
        offset=(((L-1)//64)*4+((L-1)%64)//16)*self.kheads*self.dim*4
        n=self.kheads*self.dim*4;addr=self.ext.layout.address(name,offset,n)
        if (L-1)%16:
            t=self.ranges(t,[(addr,n)],'summary_update')
        t=self.op(t,'summary_update',vec=self.kheads*self.dim)
        start=t;t=self.ext.access(t,n,'ATT_summary',True,address=addr)
        self.record('DRAM_summary_update_write',start,t,address=addr,bytes=n,resource='external_memory')
    addr=self.ext.layout.address(name,0,size)
    t=self.ranges(t,[(addr,size)],'summary_read')
    t=self.scratch(t,write=size,kind='summary');t=self.scratch(t,read=size,kind='summary')
    # Sum-to-mean conversion shared by the Q heads in a GQA group.
    t=self.op(t,'summary_means',vec=self.kheads*math.ceil(L/16)*self.dim,nl=math.ceil(L/16))
    return t,size
```

## attention_tlm_v3.py:249-272

```python
def qk_tiles(self,t,L,layer,rows,fused_pv=False):
    sets=[set(r['indices']) for r in rows]
    for offset in range(0,L,self.ac['kv_tile_tokens']):
        end=min(L,offset+self.ac['kv_tile_tokens']);ranges=[];active=0
        for k in range(self.kheads):
            union=set().union(*sets[k*self.group:(k+1)*self.group])
            for index in sorted(i for i in union if offset<=i<end):
                ranges.append((self.kv_address(layer,index,k),self.vecbytes))
                if fused_pv:ranges.append((self.kv_address(layer,index,k,True),self.vecbytes))
        for s in sets:active+=sum(offset<=i<end for i in s)
        if not active:continue
        t=self.ranges(t,ranges,'KV_fused' if fused_pv else 'K')
        size=sum(n for _,n in ranges)
        t=self.scratch(t,write=size,kind='KV_tile');t=self.scratch(t,read=size,kind='KV_tile')
        t=self.op(t,'QK',mac=active*self.dim,vec=active)
        if fused_pv:
            # Streaming log-sum-exp + online weighted accumulator rescaling.
            live=sum(any(offset<=i<end for i in s) for s in sets)
            t=self.op(t,'online_softmax',vec=4*active+live*(2*self.dim+3),nl=active+live)
            t=self.op(t,'PV',mac=active*self.dim)
        else:
            t=self.scratch(t,write=active*4,kind='logits')
    if fused_pv:t=self.op(t,'online_finalize',vec=self.qheads*self.dim,nl=self.qheads)
    return t
```

## attention_tlm_v3.py:91-111

```python
def ranges(self,t,ranges,kind):
    """Align actual addresses, deduplicate physical bursts within this DMA.

    Sparse V reads pay burst overfetch and per-DMA latency; no N/L multiplier.
    Different DMAs are not assumed to have a free DRAM cache.
    """
    burst=64 if self.cfg['external_memory'].get('backend')=='dramsys' else self.cfg['external_memory']['burst_bytes']
    lines=set();useful=sum(n for _,n in ranges)
    for address,size in ranges:
        lines.update(range(address//burst,(address+size-1)//burst+1))
    runs=[]
    for line in sorted(lines):
        if runs and line==runs[-1][-1]+1:runs[-1].append(line)
        else:runs.append([line])
    self.traffic['attention_'+kind+'_useful_bytes']+=useful
    self.traffic['attention_'+kind+'_physical_bytes']+=len(lines)*burst
    for run in runs:
        addr=run[0]*burst;n=len(run)*burst;start=t
        t=self.ext.access(t,n,'ATT_'+kind,False,address=addr)
        self.record('DRAM_'+kind,start,t,address=addr,bytes=n,resource='external_memory')
    return t
```

## memory_schedule_v5.py:121-164

```python
def qk_tiles(self,t,L,layer,rows,fused_pv=False):
    tile=self.ac['kv_tile_tokens'];blocks=math.ceil(L/tile)
    if self.ac['mode']=='dense':
        active=[self.qheads*min(tile,L-i*tile) for i in range(blocks)]
        live=[self.qheads]*blocks;grouped=None
    else:
        active=[0]*blocks;live=[0]*blocks;grouped=[[set() for _ in range(self.kheads)] for _ in range(blocks)]
        head_counts=[[0]*self.qheads for _ in range(blocks)]
        for row in rows:
            seen=set();group=row['head']//self.group
            for index in row['indices']:
                b=index//tile;active[b]+=1;seen.add(b);grouped[b][group].add(index)
                head_counts[b][row['head']]+=1
            for b in seen:live[b]+=1
    head_cursors=[0]*self.qheads
    for b,amount in enumerate(active):
        if not amount:continue
        offset=b*tile;n=min(tile,L-offset)
        if grouped is None:
            address=self.ext.layout.address(f'L{layer}/KV',offset*self.ext.layout.kv_token_bytes,n*self.ext.layout.kv_token_bytes)
            ranges=[(address,n*self.ext.layout.kv_token_bytes)]
        else:
            ranges=[]
            for k,indices in enumerate(grouped[b]):
                for index in sorted(indices):
                    ranges.append((self.kv_address(layer,index,k),self.vecbytes))
                    if fused_pv:ranges.append((self.kv_address(layer,index,k,True),self.vecbytes))
        t=self.ranges(t,ranges,'KV_fused' if fused_pv else 'K')
        size=sum(n for _,n in ranges)
        t=self.scratch(t,write=size,kind='KV_tile');t=self.scratch(t,read=size,kind='KV_tile')
        t=self.op(t,'QK',mac=amount*self.dim,vec=amount)
        if fused_pv:
            t=self.op(t,'online_softmax',vec=4*amount+live[b]*(2*self.dim+3),nl=amount+live[b])
            t=self.op(t,'PV',mac=amount*self.dim)
        else:
            for head,count in enumerate(head_counts[b]):
                if count:
                    address=self.arena['logits'][0]+head*L*4+head_cursors[head]*4
                    t=self.work_mem.transfer(t,address,count*4,True,'QK_head_logits')
                    self.traffic['attention_scratch_write_bytes']+=count*4
                    head_cursors[head]+=count
            self.attn_port.free=t
    if fused_pv:t=self.op(t,'online_finalize',vec=self.qheads*self.dim,nl=self.qheads)
    return t
```

## pv_stream_v6.py:181-266

```python
def attention(self, ready, length, layer):
    if self.ac['mode'] == 'dense':
        return super().attention(ready, length, layer)
    if max(self.weights.slot_free) > ready + 1e-5:
        raise ValueError('weight staging has not released shared SRAM')
    self.attention_length = length
    token = self.attn_calls[layer]
    self.attn_calls[layer] += 1
    self.coord = dict(token=token, layer=layer)
    block = self.ac['kv_tile_tokens']
    tiles = math.ceil(length / block)
    samples = context_samples(length, self.pc)
    if samples > 65535:
        raise ValueError('16-bit sample count overflow')
    # Disjoint regions, finite count/V buffers. No uniform-word SRAM.
    sizes = [('state', self.qheads * self.dim * 4 + 8192),
             ('KV', 2 * block * self.kheads * self.vecbytes),
             ('scores', self.qheads * length * 4),
             ('stats', self.qheads * tiles * 16),
             ('counts', self.group * block * 2 + block * 4 + 64),
             ('V', block * self.vecbytes),
             ('descriptors', self.pc['max_spans_per_descriptor'] * 16 +
              self.pc['dma_pending_bursts'] * 16)]
    self.arena = {}
    cursor = 0
    for name, size in sizes:
        cursor = math.ceil(cursor / 64) * 64
        self.arena[name] = (cursor, size)
        cursor += size
    self.attn_peak = max(self.attn_peak, cursor)
    self.attn_work_peak = max(self.attn_work_peak, cursor)
    if cursor > self.work_mem.capacity:
        raise ValueError('v6 working set exceeds SRAM')
    start = ready
    t = ready
    counts = []
    # Numerical fixture/oracle, not additional hardware dense computation.
    for head in range(self.qheads):
        probabilities = softmax(self.source.logits(token, layer, head, length))
        offset = self.source.random(token, layer, head, 'pv_v6_systematic').random()
        counts.append(systematic_counts(probabilities, samples, offset))
    possible = self.qheads * length
    self.actions['ATT_selected_QK_tokens'] += possible
    self.actions['ATT_possible_QK_tokens'] += possible
    # Pass 1: K only, complete QK, per-tile exponents/statistics, no V prefetch.
    before = t
    for offset in range(0, length, block):
        n = min(block, length - offset)
        spans = [(self.kv_address(layer, i, 0), self.kheads * self.vecbytes)
                 for i in range(offset, offset + n)]
        t = self.ranges(t, spans, 'K')
        size = n * self.kheads * self.vecbytes
        t = self.transfer(t, 'KV', size, True, 'K_tile_fill')
        t = self.transfer(t, 'KV', size, False, 'K_tile_operand')
        amount = n * self.qheads
        t = self.op(t, 'QK', mac=amount * self.dim, vec=amount)
        t = self.op(t, 'tile_softmax_stats', vec=3 * amount + 3 * self.qheads,
                    nl=amount + self.qheads)
        t = self.transfer(t, 'scores', amount * 4, True, 'score_stash',
                          offset=offset * self.qheads * 4)
        t = self.transfer(t, 'stats', self.qheads * 16, True, 'tile_stats',
                          offset=(offset // block) * self.qheads * 16)
    t = self.phase('score_and_tile_stats', before, t)
    # Global tile mass scan yields exact integer budgets from each head's
    # single systematic phase. Counts sum to S, not rounded S per tile.
    before = t
    t = self.transfer(t, 'stats', self.qheads * tiles * 16, False, 'budget_stats')
    t = self.op(t, 'tile_mass_rescale', vec=3 * self.qheads * tiles,
                nl=self.qheads * (tiles + 1))
    t = self.random_words(t, self.qheads, 'systematic_offsets')
    t = self.prefix_scan(t, 'tile_budget_prefix', tiles, heads=self.qheads)
    t = self.transfer(t, 'stats', self.qheads * tiles * 16, True, 'budgets_and_phase')
    t = self.phase('budget_and_rng', before, t)
    self.actions['ATT_V_sample_events'] += self.qheads * samples
    self.actions['ATT_V_additions'] += self.qheads * samples * self.dim
    self.actions['ATT_V_unique_head_indices'] += sum(map(len, counts))
    # Pass 2: by KV group then tile. Read each union V row once, broadcast
    # to participating heads, retain repeated additions for multiplicities.
    for kvhead in range(self.kheads):
        heads = range(kvhead * self.group, (kvhead + 1) * self.group)
        for offset in range(0, length, block):
            n = min(block, length - offset)
            per_head = [{i: c for i, c in counts[h].items() if offset <= i < offset + n}
                        for h in heads]
            live = [j for j, values in enumerate(per_head) if values]
            if not live:
```
