`timescale 1ns/1ps
module rtl_suite;
reg clk=0;always #4 clk=~clk;
reg rst=0;
reg [63:0] din=0;reg iv=0,il=0;wire ir;reg [7:0] ik=255,ist=255;
wire [63:0] dout;wire ov,ol;wire [7:0] ok,os;reg ready=1;
reg [5:0] awaddr=0,araddr=0;reg awvalid=0,wvalid=0,arvalid=0;
reg [31:0] wdata=0;wire awready,wready,bvalid,arready,rvalid;wire [31:0] rdata;
wire [1:0] br,rr;
qgemv dut(.ap_clk(clk),.ap_rst_n(rst),
.in_r_TDATA(din),.in_r_TVALID(iv),.in_r_TREADY(ir),.in_r_TLAST(il),.in_r_TKEEP(ik),.in_r_TSTRB(ist),
.out_r_TDATA(dout),.out_r_TVALID(ov),.out_r_TREADY(ready),.out_r_TLAST(ol),.out_r_TKEEP(ok),.out_r_TSTRB(os),
.s_axi_control_AWADDR(awaddr),.s_axi_control_AWVALID(awvalid),.s_axi_control_AWREADY(awready),
.s_axi_control_WDATA(wdata),.s_axi_control_WSTRB(4'hf),.s_axi_control_WVALID(wvalid),.s_axi_control_WREADY(wready),
.s_axi_control_BRESP(br),.s_axi_control_BVALID(bvalid),.s_axi_control_BREADY(1'b1),
.s_axi_control_ARADDR(araddr),.s_axi_control_ARVALID(arvalid),.s_axi_control_ARREADY(arready),
.s_axi_control_RDATA(rdata),.s_axi_control_RRESP(rr),.s_axi_control_RVALID(rvalid),.s_axi_control_RREADY(1'b1),.interrupt());
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
reg [63:0] idata[0:255],expected[0:255];
integer ilast[0:255],ikeep[0:255],istrb[0:255],gate[0:255];
integer elast[0:255],ekeep[0:255],estrb[0:255],required[0:255],isheader[0:255];
integer ni,no,eh,ee,et,consumed,count,fd,rc,caseindex,mode=0;
integer inputs=0,outputs=0,cycle=0,startcycle,stalls=0,hstalls=0,pstalls=0,laststalls=0,waitvalid=0;
integer afterassert=0,readyidx=-1,holdcycles=0,lowrun=0;
integer logfd,seed=32'h6a09e667;string name,fixture,logpath;
reg active=0,wasblocked=0,completed=0;
reg observed_pending=0,before_valid=0;reg [80:0] withdrawn_beat,before_beat;integer total_h=0,total_p=0,total_last=0,total_after=0;reg [80:0] held;
wire [80:0] beat={ol,os,ok,dout};
always @(posedge clk) begin
 cycle=cycle+1;
 if(rst && active)begin
  if(cycle-startcycle>10000)$fatal(1,"BOUND scenario=%s mode=%0d cycle=%0d",name,mode,cycle);
  if(observed_pending && (ov!==1'b1 || beat!==withdrawn_beat))
   $fatal(1,"STABILITY_WITHDRAW scenario=%s mode=%0d cycle=%0d time=%0t: VALID observed before READY withdrawal; valid=%b ready=%b expected=%h actual=%h",name,mode,cycle,$time,ov,ready,withdrawn_beat,beat);
  observed_pending=0;
  if(wasblocked && (ov!==1'b1 || beat!==held))
   $fatal(1,"STABILITY scenario=%s mode=%0d cycle=%0d time=%0t expected=%h actual=%h valid=%b ready=%b",name,mode,cycle,$time,held,beat,ov,ready);
  wasblocked=ov&&!ready;held=beat;
  if(iv&&ir)begin
   if(inputs>=consumed)$fatal(1,"ERROR_DRAIN scenario=%s cycle=%0d",name,cycle);
   if(outputs<gate[inputs])$fatal(1,"PREFETCH scenario=%s cycle=%0d inputs=%0d outputs=%0d gate=%0d",name,cycle,inputs,outputs,gate[inputs]);
   inputs=inputs+1;
  end
  if(ov)begin
   if(outputs>=no)$fatal(1,"EXTRA_OUTPUT scenario=%s cycle=%0d",name,cycle);
   if(inputs<required[outputs])$fatal(1,"PREMATURE_OUTPUT scenario=%s cycle=%0d",name,cycle);
   if(beat!=={1'(elast[outputs]),8'(estrb[outputs]),8'(ekeep[outputs]),expected[outputs]})
    $fatal(1,"WORD scenario=%s mode=%0d cycle=%0d index=%0d expected=%h actual=%h",name,mode,cycle,outputs,expected[outputs],dout);
   if(!ready)begin
    stalls=stalls+1;
    if(isheader[outputs])hstalls=hstalls+1;else pstalls=pstalls+1;
    if(ol)laststalls=laststalls+1;
   end else outputs=outputs+1;
  end
  // Availability bound starts only after the full command payload arrived.
  // 256 cycles exceeds installation and the longest 32-vector pipeline fill.
  if(outputs<no && inputs>=required[outputs] && !ov && !ready)waitvalid=waitvalid+1;
  else waitvalid=0;
  if(waitvalid>256)$fatal(1,"VALID_WAIT scenario=%s mode=%0d cycle=%0d time=%0t: complete payload, no VALID while READY low",name,mode,cycle,$time);
 end
end
// All stimulus changes on falling edges, away from transfer sampling.
always @(negedge clk) if(active)begin
 before_valid=ov;before_beat=beat;
 if(readyidx!=outputs)begin readyidx=outputs;holdcycles=0;end
 case(mode)
  0:begin // low before availability, then hold VALID for five sampled edges
   if(holdcycles<5)begin ready=0;if(ov)holdcycles=holdcycles+1;end
   else ready=1;
  end
  1:begin // READY initially high; withdraw it AFTER observing VALID
   if(holdcycles==0)begin
    ready=1;
    if(ov)begin ready=0;holdcycles=1;afterassert=afterassert+1;end
   end else if(holdcycles<6)begin ready=0;holdcycles=holdcycles+1;end
   else ready=1;
  end
  2:ready=~ready;
  3:begin
   seed=seed^(seed<<13);seed=seed^(seed>>>17);seed=seed^(seed<<5);
   ready=(lowrun>=7)||seed[0];
   if(ready)lowrun=0;else lowrun=lowrun+1;
  end
  default:ready=1; // isolated no-stall external timing run
 endcase
 if(before_valid && !ready)begin observed_pending=1;withdrawn_beat=before_beat;end
end
integer j,k,l,unusedbase;
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 if(!$value$plusargs("FIXTURES=%s",fixture))$fatal(1,"missing fixtures");
 if(!$value$plusargs("CSV=%s",logpath))logpath="suite.csv";
 fd=$fopen(fixture,"r");if(!fd)$fatal(1,"fixture open");
 logfd=$fopen(logpath,"w");
 $fdisplay(logfd,"mode,scenario,input_transfers,output_transfers,status,stalled_cycles,header_stalls,payload_stalls,tlast_stalls,after_valid_stalls,result");
 rc=$fscanf(fd,"%d",count);
 repeat(8)@(negedge clk);rst=1;
 for(caseindex=0;caseindex<count;caseindex=caseindex+1)begin
  rc=$fscanf(fd,"%s %d %d %d %d %d %d",name,ni,no,eh,ee,et,consumed);if(rc!=7)$fatal(1,"fixture header");
  for(j=0;j<ni;j=j+1)begin
   rc=$fscanf(fd,"%d %d %d %d %d",idata[j],ilast[j],ikeep[j],istrb[j],gate[j]);if(rc!=5)$fatal(1,"fixture input");
  end
  for(j=0;j<no;j=j+1)begin
   rc=$fscanf(fd,"%d %d %d %d %d %d",expected[j],elast[j],ekeep[j],estrb[j],required[j],isheader[j]);if(rc!=6)$fatal(1,"fixture output");
  end
  @(negedge clk);inputs=0;outputs=0;stalls=0;hstalls=0;pstalls=0;laststalls=0;afterassert=0;
  readyidx=-1;holdcycles=0;lowrun=0;wasblocked=0;observed_pending=0;waitvalid=0;ready=(mode!=0);startcycle=cycle;active=1;completed=0;
  write_reg(0,1);
  fork
   begin:driver
    @(negedge clk);
    for(k=0;k<ni;k=k+1)begin
     din=idata[k];il=ilast[k];ik=ikeep[k];ist=istrb[k];iv=1;
     do @(posedge clk);while(!ir);
     @(negedge clk);
    end
    iv=0;
   end
   begin:completion
    done_status(eh,ee,et);
    // Keep offering any unread tail while checking immediate stop behavior.
    repeat(8)@(negedge clk);completed=1;
   end
  join_none
  wait(completed);disable fork;
  @(negedge clk);iv=0;
  if(inputs!=consumed || outputs!=no)$fatal(1,"COUNT scenario=%s mode=%0d cycle=%0d input=%0d/%0d output=%0d/%0d",name,mode,cycle,inputs,consumed,outputs,no);
  $fdisplay(logfd,"%0d,%s,%0d,%0d,%0d:%0d:%0d,%0d,%0d,%0d,%0d,%0d,PASS",mode,name,inputs,outputs,eh,ee,$unsigned(et),stalls,hstalls,pstalls,laststalls,afterassert);
  $display("PASS mode=%0d scenario=%s cycle=%0d words=%0d stalls=%0d",mode,name,cycle,outputs,stalls);
  total_h+=hstalls;total_p+=pstalls;total_last+=laststalls;total_after+=afterassert;
  active=0;wasblocked=0;

 end
 if(mode<4 && (total_h==0 || total_p==0 || total_last==0))$fatal(1,"COVERAGE missing stalled header/payload/TLAST");
 if(mode==1 && total_after==0)$fatal(1,"COVERAGE missing stalls after VALID");
 $display("PASS RTL suite mode=%0d activations=%0d header_stalls=%0d payload_stalls=%0d tlast_stalls=%0d after_valid_stalls=%0d",mode,count,total_h,total_p,total_last,total_after);
 $fclose(logfd);$finish;
end
initial begin #100000000;$fatal(1,"global bound");end
endmodule
