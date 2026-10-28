// Handwritten integration RTL. No changes to generated HLS RTL.
`timescale 1ns/1ps
module qgemv (
        ap_clk,
        ap_rst_n,
        in_r_TDATA,
        in_r_TVALID,
        in_r_TREADY,
        in_r_TKEEP,
        in_r_TSTRB,
        in_r_TLAST,
        out_r_TDATA,
        out_r_TVALID,
        out_r_TREADY,
        out_r_TKEEP,
        out_r_TSTRB,
        out_r_TLAST,
        s_axi_control_AWVALID,
        s_axi_control_AWREADY,
        s_axi_control_AWADDR,
        s_axi_control_WVALID,
        s_axi_control_WREADY,
        s_axi_control_WDATA,
        s_axi_control_WSTRB,
        s_axi_control_ARVALID,
        s_axi_control_ARREADY,
        s_axi_control_ARADDR,
        s_axi_control_RVALID,
        s_axi_control_RREADY,
        s_axi_control_RDATA,
        s_axi_control_RRESP,
        s_axi_control_BVALID,
        s_axi_control_BREADY,
        s_axi_control_BRESP,
        interrupt
);
localparam C_S_AXI_CONTROL_ADDR_WIDTH=6;
localparam C_S_AXI_CONTROL_DATA_WIDTH=32;
localparam C_S_AXI_CONTROL_WSTRB_WIDTH=4;
input   ap_clk;
input   ap_rst_n;
input  [63:0] in_r_TDATA;
input   in_r_TVALID;
output   in_r_TREADY;
input  [7:0] in_r_TKEEP;
input  [7:0] in_r_TSTRB;
input  [0:0] in_r_TLAST;
output  [63:0] out_r_TDATA;
output   out_r_TVALID;
input   out_r_TREADY;
output  [7:0] out_r_TKEEP;
output  [7:0] out_r_TSTRB;
output  [0:0] out_r_TLAST;
input   s_axi_control_AWVALID;
output   s_axi_control_AWREADY;
input  [C_S_AXI_CONTROL_ADDR_WIDTH - 1:0] s_axi_control_AWADDR;
input   s_axi_control_WVALID;
output   s_axi_control_WREADY;
input  [C_S_AXI_CONTROL_DATA_WIDTH - 1:0] s_axi_control_WDATA;
input  [C_S_AXI_CONTROL_WSTRB_WIDTH - 1:0] s_axi_control_WSTRB;
input   s_axi_control_ARVALID;
output   s_axi_control_ARREADY;
input  [C_S_AXI_CONTROL_ADDR_WIDTH - 1:0] s_axi_control_ARADDR;
output   s_axi_control_RVALID;
input   s_axi_control_RREADY;
output  [C_S_AXI_CONTROL_DATA_WIDTH - 1:0] s_axi_control_RDATA;
output  [1:0] s_axi_control_RRESP;
output   s_axi_control_BVALID;
input   s_axi_control_BREADY;
output  [1:0] s_axi_control_BRESP;
output   interrupt;
reg [31:0] completed_count=0;
always @(posedge ap_clk) begin
 if(!ap_rst_n) completed_count<=0;
 else if(out_r_TVALID && out_r_TREADY) completed_count<=completed_count+1'b1;
end
qgemv_core core(
 .ap_clk(ap_clk),
 .ap_rst_n(ap_rst_n),
 .in_r_TDATA(in_r_TDATA),
 .in_r_TVALID(in_r_TVALID),
 .in_r_TREADY(in_r_TREADY),
 .in_r_TKEEP(in_r_TKEEP),
 .in_r_TSTRB(in_r_TSTRB),
 .in_r_TLAST(in_r_TLAST),
 .out_r_TDATA(out_r_TDATA),
 .out_r_TVALID(out_r_TVALID),
 .out_r_TREADY(out_r_TREADY),
 .out_r_TKEEP(out_r_TKEEP),
 .out_r_TSTRB(out_r_TSTRB),
 .out_r_TLAST(out_r_TLAST),
 .s_axi_control_AWVALID(s_axi_control_AWVALID),
 .s_axi_control_AWREADY(s_axi_control_AWREADY),
 .s_axi_control_AWADDR(s_axi_control_AWADDR),
 .s_axi_control_WVALID(s_axi_control_WVALID),
 .s_axi_control_WREADY(s_axi_control_WREADY),
 .s_axi_control_WDATA(s_axi_control_WDATA),
 .s_axi_control_WSTRB(s_axi_control_WSTRB),
 .s_axi_control_ARVALID(s_axi_control_ARVALID),
 .s_axi_control_ARREADY(s_axi_control_ARREADY),
 .s_axi_control_ARADDR(s_axi_control_ARADDR),
 .s_axi_control_RVALID(s_axi_control_RVALID),
 .s_axi_control_RREADY(s_axi_control_RREADY),
 .s_axi_control_RDATA(s_axi_control_RDATA),
 .s_axi_control_RRESP(s_axi_control_RRESP),
 .s_axi_control_BVALID(s_axi_control_BVALID),
 .s_axi_control_BREADY(s_axi_control_BREADY),
 .s_axi_control_BRESP(s_axi_control_BRESP),
 .interrupt(interrupt),
 .completed(completed_count)
);
endmodule
