// Bivium-B recurrence, independent implementation; NOT a security certification.
// State [92:0]=a, [176:93]=b; first generated bit is output[0].
module rng_bivium_map(input wire [176:0] state,
 output reg [159:0] random_word, output reg [176:0] next_state);
 reg [92:0] a;
 reg [83:0] b;
 reg t1, t2, fa, fb;
 integer i;
 always @* begin
   a=state[92:0]; b=state[176:93]; random_word=0;
   t1=0; t2=0; fa=0; fb=0;
   for (i=0; i<160; i=i+1) begin
     t1=a[65]^a[92]; t2=b[68]^b[83];
     random_word[i]=t1^t2;
     fa=t2^(b[81]&b[82])^a[68];
     fb=t1^(a[90]&a[91])^b[77];
     a={a[91:0],fa}; b={b[82:0],fb};
   end
   next_state={b,a};
 end
endmodule

