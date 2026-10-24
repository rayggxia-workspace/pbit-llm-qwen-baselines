import base64,json,concurrent.futures
from github import api,push,save,PREFIX,ROOT,git
assert api('GET','/user')['login']=='jieruiz'
pr=api('GET',PREFIX+'/pulls/174')
assert pr['state']=='open' and not pr['merged'] and pr['head']['ref']=='task/173-and-direct-wd'
receipt=push();head=receipt['head']
paths=git('diff','--name-only','38de07962a05f39391a778f7b81e2ed389546bf9',head).decode().splitlines()
def verify(path):
    obj=api('GET',PREFIX+'/contents/'+path+'?ref='+head)
    assert base64.b64decode(obj['content'])==git('show',head+':'+path),path
    return path
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(verify,paths))
body='''Qwen3-4B三流AND直连Wd在单一量程下严重退化；给g/u增加固定二次幂档位后，B8/T256三seed后缀PPL从原单档7735降低至13.906（同轮BF16 13.566）。不恢复z或重新采样，sigmoid按真实g尺度进行整数移位/RNE/饱和，Wd部分和按乘积指数对齐后整数累加。

关联 #173，依赖 #172。旧单档执行098c7a00/Slurm2881和负结果保留；多档执行8249fad6/Slurm2886，45份计分/41唯一配置、36层全前缀与documents SHA通过，每片18项功能验证含CUDA整数一致性。8×128目标后缀，不是完整WT2；无训练/RTL/PPA。

| 固定g/u档位 | AND64 | AND256 | AND1024 |
|---|---:|---:|---:|
| B1 | 8949057 | 7735.00 | 30.69 |
| B2=[S,S/64] | 2482469 | 2294.61 | 未测 |
| B4=[S,S/4,S/16,S/64] | 42.34 | 14.47 | 13.71 |
| B8=[S,S/2,...,S/128] | 15.98 | 13.91 | 13.47 |

B8条件均值13.4316；BF16/旧路径/B1均值与前轮逐值相同。首层平均AND概率由0.0009104升至0.227285。B8还增加低端覆盖，不能只归因档数；1024次略低于BF16不说明能力提高。

硬件边界：A8另符号及指数，sigmoid signed8/P8+true-one LUT独立比较；相同局部scale域B4只需7种、B8需15种乘积指数。保留16位scale系数、宽整数保护位/RNE BF16。准确APC，无近似计数器误差；gate/up恢复仍FP32参考。选档/指数标签/移位/保护位有成本，无PPA结论。

报告：qwen3/results/and_direct_20261024/multiscale/REPORT_ZH.md；方法与一手文献：qwen3/and_direct/MULTISCALE_ZH.md。SUMMARY和RAW_INDEX保留每seed、全部输入/代码/配置SHA及原件路径。旧单档报告不覆盖。Projects未同步，不自动合并。
'''
api('PATCH',PREFIX+'/pulls/174',dict(title='Qwen3-4B：多档g/u与八位AND直连Wd，256次PPL改善至13.91',body=body))
api('POST',PREFIX+'/issues/173/comments',dict(body='用户授权多档扩展已完成：Slurm2886，执行8249fad6，45份计分/41唯一配置及36层全前缀SHA通过；18项服务器功能验证。B4 T64/256/1024=42.3417/14.4663/13.7139；B8=15.9779/13.9061/13.4698。BF16=13.5660，B8均值=13.4316。固定档位无在线absmax，sigmoid真实尺度整数驱动，Wd同指数部分和移位；无z重编码。新结果提交 '+head+'，见同PR174新multiscale报告。旧负结果保留。未训练、非完整WT2、无新PPA；Projects未同步，Issue保持开放待审。'))
receipt.update(pr=174,issue=173,verified_blob_count=len(verified),merged=False,ready=True,
    multiscale_results_verified=True,projects_synced=False)
save('MULTISCALE_PUBLICATION.json',receipt)
print(json.dumps(receipt))
