"""Independent finite-state checks; not author code or a model reproduction."""
from pathlib import Path
import hashlib,itertools,json,math,sys
OUT=Path(__file__).resolve().parent
def softmax(z):
    p=[math.exp(v-max(z)) for v in z];return [v/sum(p) for v in p]
def distribution(z):
    q=softmax(z);data=[]
    for path in itertools.permutations(range(3),2):
        remaining=set(range(3));prob=1.;score=[0.]*3
        for selected in path:
            den=sum(q[i] for i in remaining);prob*=q[selected]/den
            for j in remaining:score[j]+=float(j==selected)-q[j]/den
            remaining.remove(selected)
        data.append((path,prob,score))
    assert abs(sum(x[1] for x in data)-1)<1e-13
    assert max(abs(sum(prob*g[j] for _,prob,g in data)) for j in range(3))<1e-13
    return data
def objective(z,losses):return sum(prob*losses[tuple(sorted(path))] for path,prob,_ in distribution(z))
cases=0;max_fd=0.;max_rloo=0.;factor_errors=[]
loss_tables=[{(0,1):.8,(0,2):1.,(1,2):1.5},{(0,1):1.7,(0,2):.3,(1,2):1.1}]
for z in [[0.,0.,0.],[math.log(.5),math.log(.3),math.log(.2)],[1.,-.4,.8],[-1.,2.,.1],[3.,-2.,1.],[-2.,-1.,-3.]]:
    for losses in loss_tables:
        d=distribution(z)
        exact=[sum(prob*losses[tuple(sorted(path))]*g[j] for path,prob,g in d) for j in range(3)]
        fd=[]
        for j in range(3):
            plus=z.copy();minus=z.copy();plus[j]+=1e-5;minus[j]-=1e-5
            fd.append((objective(plus,losses)-objective(minus,losses))/2e-5)
        max_fd=max(max_fd,max(abs(a-b) for a,b in zip(exact,fd)))
        for m in [2,3]:
            mean=[0.]*3
            for draws in itertools.product(d,repeat=m):
                prob=math.prod(v[1] for v in draws)
                ls=[losses[tuple(sorted(v[0]))] for v in draws];bar=sum(ls)/m
                for j in range(3):mean[j]+=prob*sum((loss-bar)*v[2][j] for loss,v in zip(ls,draws))/(m-1)
            max_rloo=max(max_rloo,max(abs(a-b) for a,b in zip(exact,mean)));cases+=1
            factor_errors.append(max(abs((m-1)/m*b-a) for a,b in zip(exact,mean)))
assert max_fd<1e-8 and max_rloo<1e-12
assert max(factor_errors)>1e-3
n=8;norm=32.;den=1.5*math.sqrt(math.pi/math.log(3)*math.log(n))+1/(math.sqrt(2*math.pi)*2**(n-math.log2(n)-1))
delta=.1581;bound=(1+math.exp(math.log(n-1)-delta*norm/den))**2
needed=den*(math.log(n-1)-math.log(math.sqrt(2)-1))/norm
result={'status':'passed','scope':'independent fixed-loss categorical mathematics; no author implementation, model training/PPL/CUDA/PPA','cases':cases,'M':[2,3],'n':3,'k':2,'ordered_without_replacement':True,'full_path_iid_assumed':True,'max_finite_difference_error':max_fd,'max_RLOO_expectation_error':max_rloo,'wrong_1_over_M_detected':True,'own_loss_example':{'losses':[.8,1.,1.5],'leave_one_out_baselines':[1.25,1.15,.9],'advantages':[-.45,-.15,.6]},'independent_arithmetic':{'table4_step_increase':9.87/8.95-1,'table4_total_time_increase':5301/4376-1,'printed_initialization_bound':bound,'delta_for_bound_2':needed,'probability_bound_for_ESS_2':1-needed,'input_norm_assumption':'original Rademacher example: D=1024 gives norm32; this does not disprove the example probability'},'python':sys.version.split()[0],'note_sha256':hashlib.sha256((OUT/'READING_NOTE.html').read_bytes()).hexdigest()}
(OUT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result,ensure_ascii=False))
