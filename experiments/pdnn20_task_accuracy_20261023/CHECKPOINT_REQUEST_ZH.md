# 20层 P-DNN 权重交接清单

请提供原串联双极性 FullPath P-DNN v1 的 **20层联合训练、step1000** 版本；历史报告 N4 完整 WT2 PPL 为48.910814。该PPL只用于识别旧模型，不代替本次任务准确率。

目录名：`joint_full_path_pdnn_layers1_22_twenty_v1`。替换层：1、4–22；保留原FFN：0、2、3、23。每层输入896、隐藏4864、输出896，入口／隐藏均±1；类型`full_path_bipolar_pdnn_v1`。共20份文件，**697,875,430 bytes，约665.55 MiB**。

请发送原始 `.pt` 文件，可整体打包；不要重新`torch.save`，否则文件SHA会改变。若只有别的训练步数或0/1可学习编码版本，请附对应配置、训练步数和SHA，先确认版本，不混用。

| 文件 | Bytes | SHA-256 |
|---|---:|---|
| `best_layer1.pt` | 34893765 | `05aec8a47bd55b14d77006c01c32820d1b14f71827b980cebecf76400b2220dc` |
| `best_layer4.pt` | 34893765 | `91de63a20e6be59187275871ac85a7542017f6b1bc64a68017b66e0839049c48` |
| `best_layer5.pt` | 34893765 | `3d06843b331e531e6d77d8c05458ba0caccd1b954d7454941759440414c8c407` |
| `best_layer6.pt` | 34893765 | `c2ebc7601f4da029406892e70c72714b63ce0a30fb4acb48ec67fba6c4948dfb` |
| `best_layer7.pt` | 34893765 | `7eca2b87313181bacff7fbb8a784a9b1f942300fa352402c2b49af229f8f7097` |
| `best_layer8.pt` | 34893765 | `56eaa3a6552839ddd33f5f3a4583e806bcba90eedfabf03e6315e6ff3a73962e` |
| `best_layer9.pt` | 34893765 | `946a6430ea0f38681e462f0cf3afce8f1c7db126ccb2b4b44dbf4124422768aa` |
| `best_layer10.pt` | 34893775 | `9c5c01c96d1333731ad699a1086b0869e5063247bf6cf06838db65e57c14d9a7` |
| `best_layer11.pt` | 34893775 | `8e1185c221955930581b329fa99b8ed77a970ed13731c29a84fcb5954e3c8e62` |
| `best_layer12.pt` | 34893775 | `a12cfa7e1e4542911b751fe248e11b619c73c5ce1020f6fa207c5eb958472f37` |
| `best_layer13.pt` | 34893775 | `090c117d00f3de0bc96d37bea685d66eb0858a98f3cf2492db699cd2df1a2d55` |
| `best_layer14.pt` | 34893775 | `e609236c9a26f6a9794a916d0975ca801f03f93c8f8ccaf52879e68088a73b98` |
| `best_layer15.pt` | 34893775 | `bcdb1a35e6bebc07cca303d49188f382ea158fcbf256f3ee0f3b9a12c2348325` |
| `best_layer16.pt` | 34893775 | `b1b26202892fad2f6a80ca047e15b92a4b0aca64f2ef062fcbfa08e6844e62ff` |
| `best_layer17.pt` | 34893775 | `f79f82208c61e294ed1ae06d8a5da0e8bf04dc785dd394409a79ae4046c3179b` |
| `best_layer18.pt` | 34893775 | `5598e6fe432f45f1dc40d19ac3258d99a152550a4674f43eca5b51c225dbf2d4` |
| `best_layer19.pt` | 34893775 | `e61dc4a5c394ad3c948a5b236568c756342ad4d8ad15fbf1bbe6cef6086528fa` |
| `best_layer20.pt` | 34893775 | `798ebae6a9d01711277e31cbb11c189dacd5676b14cf1fe972940ca036689da1` |
| `best_layer21.pt` | 34893775 | `0d983aea00541ff24b07af8179440c244c59290c75da501ed56133f6583097e7` |
| `best_layer22.pt` | 34893775 | `4b838e81086abf14932738ecbf895d5e76f7ab6a15e4c0e43b5dc502d86fe4fc` |

收到后存到本人个人目录（默认接收位置）：

```text
/home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151/checkpoints/joint20/
```

将本目录的 `SHA256SUMS.expected` 放在权重目录旁，用 `sha256sum -c SHA256SUMS.expected` 核对；正式CPU预检还会检查payload层号、类型、训练phase/step、完整配置、strict state与finite tensors。不要改名或覆盖原始权重来绕过核验。模型和数据留服务器，不上传Git。
