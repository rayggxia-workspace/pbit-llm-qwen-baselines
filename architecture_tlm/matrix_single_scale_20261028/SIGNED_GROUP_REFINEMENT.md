# OR4组计数进一步收紧

v1保留正、负OR输出各自6位计数；v2在每组内先取gp-gn，再用一个7位有符号计数器累加[-32,32]。符号OR仍分别计算，未交换OR/时间顺序、未改变近似规则。每位平面16组状态从16×12位降至16×7位；和v1模式3/6独立oracle逐帧相同。新源码ss_matrix_signedgroups.sv、signed_group_tops.sv、run_group_signed.py；旧v1源码和执行包不改。M1/M8三seed功能后，仅M1追加同驻留W PPA，不重跑正常v1批次。
