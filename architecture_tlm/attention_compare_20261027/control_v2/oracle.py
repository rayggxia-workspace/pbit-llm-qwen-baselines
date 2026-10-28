"""Independent elastic-clock oracle: flat Python active-address lists, no scan RTL."""
class WinnerOracle:
    def __init__(self,n,prep=2,stream=1,cap=8,early=0):
        self.n,self.prep,self.stream,self.cap,self.early=n,prep,stream,cap,early
        self.reset()

    def reset(self):
        self.active=self.configured=self.finishing=False
        self.mask=self.winner=self.target=self.burn=0
        self.q0=self.q1=self.q2=None
        self.out_valid=False;self.out_index=0;self.done=False;self.failed=False
        self.issued=self.committed=self.consumed=self.holds=self.switches=0
        self.fair_words=self.fair_bits=self.rank_retries=self.retries=0

    def logic(self,x):
        rst,start,mask,initial,samples,burn,cfg,fvalid,bits,random_valid,word,ready=x
        pop2=self.active and self.q2 is not None and (self.committed<self.burn or not self.out_valid or ready)
        r2=self.q2 is None or pop2
        m=len(self.q1[1]) if self.q1 is not None else 0
        width=(m-1).bit_length() if m>1 else 0
        before_winner=self.winner
        if self.early and pop2:
            bitmap,selected=self.q2
            before_winner=self.winner if selected is None or bitmap>>self.winner&1 else selected
        guard=bool((self.early or not self.stream) and self.q1 is not None and self.q1[0]>>before_winner&1)
        need=m>1 and not guard
        rank=word&((1<<width)-1) if need else 0
        good=not need or rank<m
        fairready=self.active and self.q1 is not None and r2 and need
        fairfire=fairready and random_valid
        abort=fairfire and not good and self.retries+1>=self.cap
        pop1=self.active and self.q1 is not None and r2 and (not need or (random_valid and good))
        r1=self.q1 is None or pop1
        r0=(self.q0 is None or r1) if self.prep==2 else r1
        frame_ready=self.active and self.configured and not self.finishing and self.issued<self.target and r0 and (self.stream or self.issued==self.committed)
        return dict(pop2=bool(pop2),pop1=bool(pop1),r0=bool(r0),r1=bool(r1),r2=bool(r2),
                    rank=rank,width=width,m=m,fairready=bool(fairready),fairfire=bool(fairfire),abort=bool(abort),frame_ready=bool(frame_ready))

    def ports(self,x):
        l=self.logic(x)
        return list(map(int,[not self.active,self.active,self.active and not self.configured,l['frame_ready'],
             l['fairready'],self.out_valid,self.out_index,self.done,self.failed,self.winner]))

    def status(self):
        return list(map(int,[self.active,self.out_valid,self.out_index,self.done,self.failed,self.winner,
                 self.issued,self.committed,self.consumed,self.holds,self.switches,self.fair_words,self.fair_bits,self.rank_retries]))

    def edge(self,x):
        rst,start,mask,initial,samples,burn,cfg,fvalid,bits,random_valid,word,ready=x
        if not rst:self.reset();return self.status()
        l=self.logic(x);old_q0,old_q1,old_q2=self.q0,self.q1,self.q2
        old_out,old_finishing=self.out_valid,self.finishing
        self.done=False
        if self.out_valid and ready:self.out_valid=False;self.consumed+=1
        if not self.active and start:
            self.mask=mask;self.winner=initial;self.burn=burn;self.target=samples+burn
            self.active=True;self.configured=self.finishing=False
            self.out_valid=self.failed=False
            self.issued=self.committed=self.consumed=self.holds=self.switches=0
            self.fair_words=self.fair_bits=self.rank_retries=self.retries=0
            self.q0=self.q1=self.q2=None
            if not samples or not (mask>>initial&1) or self.target>0xffffffff:
                self.active=False;self.failed=self.done=True
            return self.status()
        if self.active and not self.configured and cfg:self.configured=True
        accept=bool(fvalid and l['frame_ready'])
        accepted_bitmap=bits&self.mask
        def info(bitmap):return (bitmap,[i for i in range(self.n) if bitmap>>i&1])
        if self.prep==2 and l['r0']:self.q0=accepted_bitmap if accept else None
        if l['r1']:
            value=old_q0 if self.prep==2 else accepted_bitmap if accept else None
            self.q1=info(value) if value is not None else None
        if l['r2']:
            if l['pop1']:
                bitmap,active=old_q1
                self.q2=(bitmap,active[l['rank']] if active else None)
            else:self.q2=None
        if accept:self.issued+=1
        if l['fairfire']:
            self.fair_words+=1;self.fair_bits+=l['width']
            if not (l['rank']<l['m']):self.rank_retries+=1;self.retries+=1
        if l['pop1']:self.retries=0
        if l['pop2']:
            bitmap,selected=old_q2
            new=self.winner if selected is None or bitmap>>self.winner&1 else selected
            if new==self.winner:self.holds+=1
            else:self.switches+=1
            self.winner=new
            if self.committed>=self.burn:self.out_valid=True;self.out_index=new
            self.committed+=1
            if self.committed>=self.target:self.finishing=True
        if self.active and old_finishing and (not old_out or ready):self.active=False;self.finishing=False;self.done=True
        if l['abort']:
            self.active=self.finishing=self.out_valid=False;self.failed=self.done=True
            self.q0=self.q1=self.q2=None
        return self.status()
