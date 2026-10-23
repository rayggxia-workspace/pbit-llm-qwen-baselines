"""Reanalyse existing physical records at longer lags; no new circuit run."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np


def sha(data):
    return hashlib.sha256(data).hexdigest()


def correlation(x, y):
    # Independent check below uses NumPy's covariance implementation.
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x -= x.mean()
    y -= y.mean()
    denominator = np.sqrt(np.dot(x, x) * np.dot(y, y))
    return float(np.dot(x, y) / denominator) if denominator else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--physical', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError('Keep previous signed results unchanged: ' + str(a.out))
    manifest_bytes = (a.physical / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    assert sha((a.physical / 'bits.npz').read_bytes()) == manifest['npz_sha256']
    intervals = [.5, 1, 2, 5, 10, 20, 50, 100]
    rows = []
    with np.load(a.physical / 'bits.npz', allow_pickle=False) as data:
        for record in manifest['records']:
            bits = data[record['key']]
            assert sha(bits.tobytes()) == record['bits_sha256']
            for us in intervals:
                step = round(us * 1e-6 / record['dt_s'])
                assert abs(step * record['dt_s'] - us * 1e-6) < 1e-12
                sampled = bits[::step]
                pairs = sampled[:len(sampled)//2*2].reshape(-1, 2)
                vn = pairs[pairs[:, 0] != pairs[:, 1], 0]
                full = correlation(bits[:-step], bits[step:])
                decimated = correlation(sampled[:-1], sampled[1:])
                vn_rho = correlation(vn[:-1], vn[1:])
                for x, y, value in ((bits[:-step], bits[step:], full),
                                    (sampled[:-1], sampled[1:], decimated),
                                    (vn[:-1], vn[1:], vn_rho)):
                    assert np.isclose(value, np.corrcoef(x, y)[0, 1], atol=1e-12, rtol=0)
                rows.append(dict(key=record['key'], kind=record['kind'], seed=record['seed'],
                    interval_us=us, stride=step, raw_n=len(bits), raw_p1=float(bits.mean()),
                    full_lag_pairs=len(bits)-step, rho_full_lag=full,
                    phase_zero_n=len(sampled), phase_zero_p1=float(sampled.mean()),
                    rho_phase_zero_lag1=decimated, vn_n=len(vn), vn_p1=float(vn.mean()),
                    vn_rho_output_index_lag1=vn_rho))
    assert len(rows) == 72
    summary = []
    for us in intervals:
        selected = [r for r in rows if r['kind'] != 'bare' and r['interval_us'] == us]
        summary.append(dict(interval_us=us, traces=len(selected),
            rho_full_lag_range=[min(r['rho_full_lag'] for r in selected), max(r['rho_full_lag'] for r in selected)],
            rho_phase_zero_range=[min(r['rho_phase_zero_lag1'] for r in selected), max(r['rho_phase_zero_lag1'] for r in selected)],
            phase_zero_n_per_trace=selected[0]['phase_zero_n']))
    result = dict(evidence='Reanalysis of existing Spectre 38237164, TT25C; no new EDA/digital run',
        archive_sha256=manifest['archive_sha256'], physical_manifest_sha256=sha(manifest_bytes),
        physical_npz_sha256=manifest['npz_sha256'], script_sha256=sha(Path(__file__).read_bytes()),
        python=platform.python_version(), numpy=np.__version__, intervals_us=intervals,
        retained_time_s=[manifest['discard_s'], manifest['stop_s']],
        checks=dict(physical_arrays_sha256=9, correlation_crosschecks=216),
        definitions=dict(rho_full_lag='Pearson of bits[:-k],bits[k:] on original grid; overlapping pairs, NOT independent observations',
            rho_phase_zero_lag1='Pearson of bits[::k][:-1],bits[::k][1:]; first retained time is phase zero',
            vn_rho_output_index_lag1='Adjacent retained VN outputs; physical elapsed times vary',
            ranges='Min/max of two comparator variants x three noise seeds; NOT confidence intervals'),
        summary=summary, rows=rows)
    table = '\n'.join('{:>6g} | {:>8.4f} .. {:<8.4f} | {:>8.4f} .. {:<8.4f} | {}'.format(
        r['interval_us'], *r['rho_full_lag_range'], *r['rho_phase_zero_range'], r['phase_zero_n_per_trace']) for r in summary)
    report = '''旧比较器采样间隔复核 / 2026-10-23 / Issue95、PR134

结论：原报告0.72～0.74对应0.5us采样，没有算错该场景的相关系数，但不能据此评价慢速采种工作点。
原189案例主链固定physical_sampling_s=5e-7，原物理扫间隔止于2us，覆盖不够。没有证据把0.5us当作当前物理源必须使用的采样周期。
本补充复用同一批已冻结波形，在0.5/1/2/5/10/20/50/100us重新计算；原189案例和已签SHA的报告不覆盖、不重跑。

原数据：Spectre任务38237164，TT25C，旧两款10nA比较器，每款三个seed401/503/607。每条保留2～20ms，共18ms；100ns保存步长。另重算裸源理想阈值三条作为对照，见RESULTS.json。

间隔us | 全保存点固定时间lag的rho范围 | 单一相位实际抽样rho1范围 | 每条抽样bit数
''' + table + '''

两种统计回答不同问题：
1. 全保存点固定lag：对原序列b[t]和b[t+Delta]算Pearson，使用所有可用起点。不同样本对重叠且相关，不能把对数当成独立样本量套IID置信区间。
2. 单一相位抽样：从2ms起每Delta取一个bit，再算相邻样本Pearson；它直接对应该抽样流，但长间隔的可用样本很少，结果随相位和seed波动。
范围是两款电路x三个seed的最小/最大，不是置信区间；没有拼接独立seed来伪造连续轨迹或空间通道。

10us下旧比较器固定lag相关系数约0.027～0.052，明显低于0.5us；仍有小幅残余相关，不能宣布IID。20us不保证每条记录单调更好；50/100us单相位仅360/180bit，不能拿看似很大的正负值断言长间隔更差。残余可能含低频波动，本次没有辨识其具体物理来源。
延长间隔不自动消除概率偏置：全保存点P(1)仍沿用同一原记录约44%～49%。旧VN显著负相关结论仅适用0.5us输入；长间隔VN输出数量少，仍需分别评估，不能继承原负结论或直接宣布独立。VN的lag1是相邻保留输出序号，不是固定物理时间。

架构中的三个时标必须分开：
- 本地PRNG/数字时钟：默认100MHz，即10ns。
- 同一物理源被再次取样的间隔：需显式配置并由真实读出/轮询决定，当前RandomNetwork没有建模这一模拟采样时刻。
- 本地PRNG换种：默认100000000数字拍，在100MHz约1s；这不等于种子内部相邻原始bit也隔1s。
SeedWords.interval_cycles是合格32bit字可用间隔，不是裸源bit间隔；原质量回放的1字/拍仅是预收集数据回放，不能当物理速率。
较慢平均换种允许更稀疏地收集物理bit，但若每秒突然连续高速读取256bit，包内仍可能保留短时间相关。下一轮主链应显式传入同源采样间隔、通道/行地址、真实时间戳及调理输出时间，按实际收集调度评价。

10/20us可作为本次数据支持的下一轮低速诊断候选，不是已批准默认或熵验收点。单路10us为100k原始bit/s；若近IID且p约0.5，VN理想保留率约1/4，约25k输出bit/s。这只是条件吞吐算术，不是有效熵率/实测可用速率；还需计P50校准、健康检查、调理及所有端点启动种子需求。
新高速共享电路的0.2/0.5/1us是选行槽时间；4行同源重访0.8/2/4us，不能与旧单通道连续比较器混用。真实共享比较器还须检查上一行记忆、建立时间和跨源相关，本次旧单路波形不能证明。

本次仅原波形后处理：72条记录x3相关实现交叉核对=216算术检查、9数组SHA核对通过。没有新的Spectre、数字后端/RTL、PPA、PPL运行；不记为新电路实验。没有修改正式TLM采样/换种默认；后续需按确定的物理工作点重新贯穿各层质量测量。
复现：在仓库根运行 python -m architecture_tlm.random_service.quality.review_sampling --physical C:/Users/86134/Documents/a_P_BIT/project_archives/rng_quality_20261023/physical --out <新的输出目录>
软件与准确脚本、输入SHA见本目录RESULTS.json。此分析无模型/语料/权重，相关hash不适用。
'''
    a.out.mkdir(parents=True)
    (a.out/'RESULTS.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    (a.out/'REPORT_ZH.txt').write_bytes(report.encode('utf-8'))
    print(table)
    print('9 array hashes; 216 Pearson crosschecks passed. No new simulation.')


if __name__ == '__main__':
    main()
