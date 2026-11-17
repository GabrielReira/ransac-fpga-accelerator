`timescale 1ns/1ps

module consensus_lab (
   input  wire signed [39:0] a, b, c,
   input  wire signed [39:0] x,
   input  wire signed [15:0] y,
   input  wire signed [39:0] threshold,
	input  wire        clk,
	input  wire        clear,
	input  wire        point_valid,
	input  wire [11:0] point_index,
	input  wire [11:0] read_index,
	output reg         read_inlier,
	output reg  [31:0] inlier_count,
   output wire        is_inlier
);

   // a, b, c, x e threshold usam 24 bits fracionários.
   // y é a linha da imagem, em pixels inteiros.
   wire signed [55:0] ay_plus_b;
   wire signed [71:0] predicted_x;
   wire signed [72:0] dx;

	assign ay_plus_b = a * y + b;
   assign predicted_x = ay_plus_b * y + c;
   assign dx = x - predicted_x;

   assign is_inlier = (threshold > 40'sd0) && (dx > -threshold) && (dx < threshold);

	reg decisions [0:4095];

	always @(posedge clk) begin
		 if (clear)
			  inlier_count <= 32'd0;
		 else if (point_valid && is_inlier)
			  inlier_count <= inlier_count + 32'd1;
	end

	always @(posedge clk) begin
		 if (point_valid && !clear)
			  decisions[point_index] <= is_inlier;

		 read_inlier <= decisions[read_index];
	end
	
endmodule