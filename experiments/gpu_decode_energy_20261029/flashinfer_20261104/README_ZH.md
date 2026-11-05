# FlashInfer��SDPA decode���⣨Issue212��

## 2026-11-05�û���Ȩ����ģ��̽���Բ���

������ʽ`--exploratory-whole`������ԭlogits���L2��1%��top1�ż����Ա�������δͨ����ں�֧��/������ȷ��ͨ������ģ���������ʱ�����������������ģ������256token���ɺ͹̶�CUDA Graph����ֵδͨ���Ľ����`exploratory_numerical_gate_failed`������������ջ��ߡ�������ͬ������֧�ִ���/����ʧ��/������������ɸñ�־���ǡ�

���������û����Ȼ�FlashInfer����¼����ʱ����ܺġ�����ȷ��Ȩ��2K/8K�����ظ���ԭBF16ģ��/����/�������������֣�ͬ��HF��չ��KV/ֱ��GQA����һ�������̽�����Ȳ��������ɣ��ٲ�̶�Graph�����ظ�����ɵĹ������ĻطŻ�Profiler��켣��CUDA����K/V�����Լ����������backend��������ǰ��ͬ���¶�ɸ�顣��¼����ID��ϣ���ظ�һ���ԣ���ֵδ����ʱ���������б仯��������¼��������ͬ������ܱȽϡ���ִ�п���/���������ţ���4608ԭ�����ġ�

## 2026-11-05�޸������

����ҵ4392�Ѿ�������33������Ĵ�С/SHA����manifest����ͨ����FlashInfer CUDA/Tensor��2K/8K����0.2.5��`head_dim`δ��ʼ���쳣�˳�֧�ּ�飬û�пɽ��ܵ�FlashInfer�������ݡ�ֱ��GQA������ֵ���ͨ������������ģ��logits relative-L2����Ԥ��1%������дΪ��ģ������ͨ�����·���4392�Ŷ��С�Ϊ��ʷ�ύʱ�㡣

�޸�����Ե��ýӿڣ�Qwen��scale����`1/sqrt(head_dim)`�����ϸ���֤��һ�㣬����FlashInferʹ����ȫ��ͬ��Ĭ��`sm_scale=None`��ʹ��������ʼ��head_dim������site��װ�ļ������ı�BF16 Q/K������ֵ��������Ĭ��scale��ȷ�ܾ�������Ĭ���ơ��ع����ֱ�ӵ���CUDA/Tensor������װ·����ģ���API�ĳ�ʼ����֧��

��GPUԤ��4604��ʵ�ʱ��벢����CUDA/Tensor�ںˣ�head_dim�쳣����������¶CUDA single_decode�Դ�padding���������汨`k must be contiguous`���ʸ�ʧ�ܿ��ձ�����δ����������4605���ء�����v4����CUDA·��ִ��K/V.contiguous��ʵ�ʸ���λ�ڼ�ʱ/���������ڲ��������Ԥ������Tensor·������ֱ�ӽ���HND stride���˴����ǰ�KVչ��Ϊ32ͷ��

�¿��ն��Ᵽ��`HF_ORIGINAL_NATIVE.json`��δ��װAttention Adapter�Ĺٷ�HF SDPA/DynamicCache����256�����ɣ��ų�prefill������չ��KV�ľ�̬����Adapter��ֱ��GQA��FlashInfer��·���ֿ����档�̶�CUDA Graphǰ���Բ������������ɡ�

����`--preflight-only`��ִ��2K/8K��֧������ֵ��飬������ʽʱ��/������֧���쳣���ط�������ֹ������ҵ��CPU���ԡ�GPUԤ�졢��ʽGPU��ҵͨ��Slurm afterok��������������ԭ�ż���ʧ���嵥��������Ϊֱ��GQA��FlashInfer�ſ����ɻ���/�ɿ���/�ɽ�������ǣ�׼ȷ����ҵ��״̬������ר�Ż�ִ��

�û���Ȩ����д�ű���ͨ��Slurm�ύ���⡣��3399/3440/3443���价����Դ�롢����������ġ����β�ѵ����������������PPL�����������GPU�������档

## �Ƚ�����

Qwen/Qwen3-4B��ѵ���棬revision `1cfa9a7208912126459214e8b04321603b3df60c`��ԭBF16��B1��2K/8K��32Q/8KVͷ��head_dim128������ԭģ��/�ִ���/������token SHA������ǰ���ļ����飬����Slurm�����RTX5090��ͬһ������Բ�������ʹ��TDP����������

| ��� | ���� |
|---|---|
| sdpa_expanded | ��װ��HFͬ����repeat_kv��ǿ��PyTorch Flash SDPA |
| sdpa_gqa | ǿ��Flash SDPA��ֱ��enable_gqa=True |
| flashinfer_cuda | FlashInfer single_decode��ԭ��8��KVͷ��CUDA-core·�� |
| flashinfer_tensor | ͬ�ϣ�use_tensor_cores=True��FA2·�� |

��������Torch2.7.1+cu128/Transformers4.51.3������Ŀ¼������װ����FlashInfer0.2.5/ninja1.11.1.4��������ԭ�������ù̶������汾���ڸ�����Ӱ�죬�����ƴ������°�FlashInfer/vLLM/SGLang����ѱ��֡�Դ����ӹٷ�PyPI��ȡ������SHA���״�CUDA JIT��������ֵԤ��׶Σ�����ʱ�䲻������ʽ���ڡ�

## ʵ�ʲ�ʲô

1. ����36��ģ�͹̶���token CUDA Graphǰ��ÿ���/������10���3���ų�prefill��argmax��������������ͬ���Graph/eagerҪ��logits��λһ�¡�
2. ����ģ������̰��decode��ÿ��256����3������argmax��KV��ǰλ�ø��¼��������������ų�prefill���������ڲ���3��ʱ��ȷ�����ţ����������������
3. Attention���ģ�ʹ��δ�Ķ�ģ��ȫ��36�����ʵQ/K/V���룬5���3�����طţ���ʱ��/�����������ð������ģ�͡�
4. ����Profiler����ںˡ�36�㸲�Ǻ�14��ģ��kernelʱ�䡣Profiler�׶ζ������������׮ʱ����Ϊ���ӳ١�����CORE_TRACE����ģ��TRACE�ֿ����档

������ֵΪNVML�ۼ�������������������Դ棻���ظ��������ʻ���һ������ϡ���¼�¶ȡ�SM/�Դ�Ƶ�ʡ�Ԥ���ȶ��ԣ��Ȳ���ƵҲ���ٳƺ��£�����NVML�ӿڲ��Ƕ����������ʹ��Slurm����GPU�����ܾ�ͬ������������̡�

## ��ֵ�Ž�

- �������ص�����ʵ�ı�λ�ã����к��ʹ��ͬһԭģ��KV������token��ԭSDPA��̬����·������bitwise��ͬ��������˱���ԭrelative-L2��1%��top1��ͬ�ż�����Ϊ����ʷGQAʧ��ͨ�����ſ���
- ����decode���ýϴ�����HND������в�ͬhead stride��v2���Ӵ�padding��ͬһ��ʵ�ӿڼ���������������¼�飬��ֹֻ��֤���չ̶����档
- �Ե�һ/�м�/�������룬����FP32 math SDPA������Attention���oracle��relative-L2��1%����ֻ����ֵ��ȷ�Լ�飬����FP32 oracle��ʵ�ʸ�Ч���ߡ�
- ��Ӧ��RoPE/QK-Norm��Q/K�����ںˣ�FlashInfer����pos_encoding_mode=NONE����������д����Чǰ׺������δʹ�û���۵���ʵK/V��
- δͨ����ֵ/֧�ּ��ĺ�˵������ԭ�򣬲�������ܵ���ģ�����ܽ����������˼�������ʽ���״̬����ʧ���嵥�����Ѳ��ֺ�˳ɹ�д��ȫ��ͨ����

## ��ǰ�ύ״̬

CPU4388��COMPLETED/0:0/11�룺���밲װ��6��CPU����ͨ����Torch���䣬FlashInferʹ��JIT��ˡ��״�GPU4389��δ��������v2�����δ����GPU����ʱ�䣬�ɰ�/��ִ������**��ǰ��ЧGPU��ҵ4392**����5090��4CPU��48GiB��1Сʱ���ޣ��Ŷ��У�����������ɰ�װ��

v2ִ�а�SHA `5e5f0f324f84bdeb7cc73e50bd04083aa3b0d03bedeccffff06c4c0d92322f11`��manifest SHA `d2afc2b2239ecfb66f31837fe456365040ba117cb303c7a7050d53536d2ee5d8`��ÿrun������롢���á�׼���嵥��Ȩ�غ�����SHA�����ARTIFACT_MANIFEST��COMPLETED.json��棻��trace�����и��˷������洢��Git��������С�����

�����Ӷ�����ս���AST/���ļ�SHA��鼰6��CPU����ͨ����GPU��ȷ�ԡ������ںˡ�ʱ���������д���ҵ���С����ѡ���װͨ��/�����ύ��д�ɡ�GPU����֤���������FlashInfer����HF����ģ�͵ĺ�����ڣ������������������赥��������

## ���

������`bench.py --root <����Դ��Ŀ¼> --prepared <ԭ׼���嵥> --output <�½��Ŀ¼>`������CONFIG.json����������Issue212ԭ�������Դ�룬controlled_remeasure.load_dependencies��SHA��֤���ύ/���ʵı���·�����ִ������HANDOFF��������ƾ�ݻ��������ʷ��

���Ʋο���[FlashInfer�̶��汾decodeԴ��](https://github.com/flashinfer-ai/flashinfer/blob/v0.2.5/flashinfer/decode.py)��[�ٷ�PyPI�汾](https://pypi.org/project/flashinfer-python/0.2.5/)��[PyTorch SDPA](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html)��
