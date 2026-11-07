## 2026-11-07 完整结果已收齐，覆盖下方运行中记录
38617087两项完整36层＋lm_head已status=completed，RESULT/SEAL/冻结源SHA核验。T64/64为51.43301ms含头、7.07502头、44.35799扣头；T8/32为51.40648/7.07546/44.33102ms。8个prefix/full原件已逐字节归档；COMPLETED_RESULTS_ZH.md和JSON为最新结果，未重跑。此结果不含新Attention PV128/归约32/QK共享。新完整T64profile快估T8误差单点约−.02531ms/−.0492%，不泛化为通用精度保证。无须继续等待原数组或重交；旧SOURCE_MANIFEST保留历史字节身份。
新Attention候选的接入及条件面积另见work/rayggxia/225/attention_candidate_20261107/HANDOFF.md。

---

# Issue225：可调采样时间与lm_head分列

2026-11-06，负责人rayggxia；task/225-norm-stream-20261106、PR248，工作目录tmp/norm-stream-issue225-20261106。用户要求前级Wg/Wu T8、非线性三AND直连Wd T32的时间预估、可快速扫采样次数的脚本，并检查恢复后的服务器。现已完成脚本、原生两层配对与旧完整结果核验；新完整两项正在运行，不冒充完成。

## 正式成果

architecture_tlm/sampling_latency_20261106/README_ZH.md、fastsim.py、model.py、run.py。fastsim只需Python标准库，六组扫描约0.7秒；默认REFERENCE_PROFILE是已封存1952KiB/1024FMA/T64/T64，当前1216KiB/640候选用CURRENT_PREFIX_PROFILE显式选择。后者是两层×18与旧6.95415ms lm_head代理，非新完整测得结果。

旧完整38616054两项已COMPLETED/0:0，原生RESULT/SEAL SHA本地与服务器一致。b96s96含头49.93827ms、lm_head6.95415ms、扣头42.98412ms；control502为49.95081/6.95415/42.99666ms。不得把这组标成1216KiB/640结果。

当前粗估前64后64为51.30ms含头/44.35ms扣头，前8后32约51.25/44.29ms；有效精度只到约51/44ms。两层原生实际2.46395→2.46201ms（−0.0787%），GU＋NL_Wd1.25171→1.24790ms（−0.3044%），外存均257484544B；MAC/跨K/Attention动作相同，GU随机动作为1/8、后级为1/2已核。没有因减少T把所有延迟/面积/能量按比例缩放。

模型每帧旧66拍，新GU8为10拍100ns、NL_Wd32为34拍340ns；其他delay不变。实际TLM通过实例delay改变服务时间，修正旧actor660ns常量统计和R8计数。仍12核、96KiB宽状态、32权重槽、两个累加端口、1216KiB/304bank、640普通池、K128/赢家S64。时序是原协议可变T宏假设，无新电路PPA或模型PPL，不把旧T64能量表应用到T8/T32。

“不含lm_head”目前定义为总时间减lm_head阶段，保留final norm及已重叠预取；不是完全取消头权重搬运的无头硬件重跑。用户主表要同时列含头/扣头，另列头阶段，不混称。

## 远端状态与恢复

新独占快照：/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm225_sampling_latency_20261106/4528b0b42a97，identity4528b0b42a97b8dbd601f96a278b7f219710e220334ee4236dc1a0aa529daf8f。固定旧runtime manifest SHA7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40。20只读依赖manifest SHA a633d11f4a52d47611a96cd8016695f47294d154cb900bec2b4edac914d90291，原件本地project_archives/sampling_latency225_20261106/dependencies；不复制到Git。

38617085七项EDA门禁COMPLETED/0:0；38617086_[0-1]两层配对COMPLETED/0:0；38617087_[0-1]完整36层＋lm_head已RUNNING（最新STATUS实际阶段为首层）。1CPU/任务、0GPU，最多2并行，12GiB/8h上限；预计按已测墙钟约2—2.5小时完成，队列和节点吞吐变化可延长。不要把sacct展开的38617089/38617132等数组子ID当新提交，按SUBMISSION数组索引核对。

旧1216失败计划无作业，不再另交一套；198 TT250与204其他任务均不干预。无自动化/回查任务。恢复：先重读最新Issue225/PR248/STATUS，再`ops.py status`、`collect`，只计status=completed且SEAL和冻结源SHA通过的结果，随后`archive`保留原字节。健康任务不重交，已提交源不能编辑。

原始两层RESULT/SEAL已SFTP逐字节归档project_archives/sampling_latency225_20261106/native/prefix/{T64_64,T8_32}/，摘要NATIVE_PREFIX_RESULTS.json、逐SHA索引ARCHIVE.json。源提交与结果交付见PUBLICATION.json；未有回执不得写远端已交付。新源与旧依赖SHA在VALIDATION/SUBMISSION，旧执行快照只读。

完成后用make_profile.py从新T64的RESULT/SEAL生成当前完整profile，替换两层外推；重新跑fastsim与新T8完整时间作校验，明确模型误差，更新相同PR/Issue/STATUS/备忘录。普通lm_head阶段单独更新，不能继续沿用旧1024路代理。Projects无写接口待维护者同步，PR待审不合并。
