`timescale 1ns/1ps
module rtl_stress;
reg clk=0;always #4 clk=~clk;
reg rst=0;
reg [63:0] din=0;reg iv=0,il=0;wire ir;
wire [63:0] dout;wire ov,ol;wire [7:0] ok,os;reg ready=1;
reg [5:0] awaddr=0,araddr=0;reg awvalid=0,wvalid=0,arvalid=0;
reg [31:0] wdata=0;wire awready,wready,bvalid,arready,rvalid;wire [31:0] rdata;
wire [1:0] br,rr;
qgemv dut(.ap_clk(clk),.ap_rst_n(rst),
.in_r_TDATA(din),.in_r_TVALID(iv),.in_r_TREADY(ir),.in_r_TLAST(il),.in_r_TKEEP(8'hff),.in_r_TSTRB(8'hff),
.out_r_TDATA(dout),.out_r_TVALID(ov),.out_r_TREADY(ready),.out_r_TLAST(ol),.out_r_TKEEP(ok),.out_r_TSTRB(os),
.s_axi_control_AWADDR(awaddr),.s_axi_control_AWVALID(awvalid),.s_axi_control_AWREADY(awready),
.s_axi_control_WDATA(wdata),.s_axi_control_WSTRB(4'hf),.s_axi_control_WVALID(wvalid),.s_axi_control_WREADY(wready),
.s_axi_control_BRESP(br),.s_axi_control_BVALID(bvalid),.s_axi_control_BREADY(1'b1),
.s_axi_control_ARADDR(araddr),.s_axi_control_ARVALID(arvalid),.s_axi_control_ARREADY(arready),
.s_axi_control_RDATA(rdata),.s_axi_control_RRESP(rr),.s_axi_control_RVALID(rvalid),.s_axi_control_RREADY(1'b1),.interrupt());
integer inputs=0,outputs=0,phase=0,blocked=0;reg [63:0] held;reg wasblocked=0;
always @(posedge clk) if(rst) begin
 if(iv&&ir) inputs=inputs+1;
 if(wasblocked && (!ov || dout!==held || ol!==1'b1 || ok!==8'hff || os!==8'hff)) $fatal(1,"unstable output under backpressure");
 wasblocked=ov&&!ready;held=dout;
 if(ov&&!ready) blocked=blocked+1;
 if(ov&&ready) begin
  if(phase!=3) $fatal(1,"unexpected error output");
  if(!ol || ok!=255 || os!=255) $fatal(1,"bad framing");
  case(outputs)
   0:if(dout!==64'd7)$fatal(1,"config echo");
   1:if(dout!==64'd8)$fatal(1,"process echo");
   2:if(dout!==64'h07f400080314fb0a)$fatal(1,"identity output");
   default:$fatal(1,"extra output");
  endcase
  outputs=outputs+1;
 end
end
task write_reg(input [5:0] addr,input [31:0] data);
 begin
 @(negedge clk);awaddr=addr;awvalid=1;
 do @(posedge clk);while(!awready);
 @(negedge clk);awvalid=0;wdata=data;wvalid=1;
 do @(posedge clk);while(!wready);
 @(negedge clk);wvalid=0;
 wait(bvalid);@(negedge clk);
 end
endtask
task read_reg(input [5:0] addr,output [31:0] data);
 begin
 @(negedge clk);araddr=addr;arvalid=1;
 do @(posedge clk);while(!arready);
 @(negedge clk);arvalid=0;
 wait(rvalid);data=rdata;@(negedge clk);
 end
endtask
reg [31:0] value;
task done_status(input [31:0] h,input [31:0] e,input [31:0] id);
 begin
 value=0;
 while(!value[1]) read_reg(0,value);
 read_reg('h10,value);if(value!==h)$fatal(1,"halted");
 read_reg('h20,value);if(value!==e)$fatal(1,"error");
 read_reg('h30,value);if(value!==id)$fatal(1,"tx_id");
 end
endtask
task send(input [63:0] data,input last);
 begin
 @(negedge clk);din=data;il=last;iv=1;
 do @(posedge clk);while(!ir);
 @(negedge clk);iv=0;
 end
endtask
task hdr(input [31:0] op,input [31:0] id,input [31:0] param);
 begin send(op,0);send(id,0);send(param,1);end
endtask
integer base,i;
initial begin

 repeat(8)@(negedge clk);rst=1;
 phase=1;write_reg(0,1);
 // Decodable bad transaction-ID TLAST; later parameter is already offered.
 send(1,0);send(55,1);
 @(negedge clk);din=0;il=1;iv=1;
 done_status(1,1,55);repeat(8)@(negedge clk);
 if(inputs!=2)$fatal(1,"consumed after malformed header");iv=0;
 $display("PASS malformed header leaves offered later word unaccepted");
 phase=2;write_reg(0,1);hdr(2,56,1);done_status(1,5,56);
 if(outputs!=0)$fatal(1,"error output");
 $display("PASS fresh activation rejects PROCESS before CONFIG");
 phase=3;write_reg(0,1);
 // Missing data blocks without timeout, then valid CONFIG recovers.
 repeat(40)@(negedge clk);
 if(outputs!=0)$fatal(1,"output without input");
 hdr(1,7,0);
 for(i=0;i<8;i=i+1)send(64'h1<<(8*i),0);
 send(0,0);send(0,1);
 hdr(2,8,1);send(64'h07f400080314fb0a,1);
 base=inputs;
 fork
  begin
   // Stall result output, while the next END header is offered.
   wait(outputs==2);@(negedge clk);ready=0;
   repeat(40)@(negedge clk);
   if(!ov)$fatal(1,"AXI compliance: TVALID waits for TREADY");
   repeat(12)@(negedge clk);
   if(inputs!=base)$fatal(1,"accepted next header before last result");
   ready=1;
  end
  begin hdr(3,99,0);end
 join
 done_status(0,0,0);
 if(outputs!=3 || blocked<10)$fatal(1,"missing stress coverage outputs=%0d blocked=%0d",outputs,blocked);
 $display("PASS input blocking, stable output backpressure, no prefetch, successful END, blocked_cycles=%0d",blocked);
 $display("PASS RTL stress completed");$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
