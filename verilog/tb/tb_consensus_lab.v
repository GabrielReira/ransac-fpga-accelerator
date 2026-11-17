`timescale 1ns/1ps

module tb_consensus_lab;
	wire is_inlier;
	wire [31:0] inlier_count;
	wire read_inlier;
	
	reg signed [39:0] a, b, c, x, threshold;
	reg signed [15:0] y;
	reg clk = 1'b0;
	reg clear;
	reg point_valid;
	reg [11:0] point_index;
	reg [11:0] read_index;
	
	integer errors;

	always #5 clk = ~clk;
	 
	consensus_lab dut (
        .a(a),
        .b(b),
        .c(c),
        .x(x),
        .y(y),
        .threshold(threshold),
		  .clk(clk), 
		  .clear(clear), 
		  .point_valid(point_valid),
		  .point_index(point_index),
		  .read_index(read_index),
		  .read_inlier(read_inlier),
		  .inlier_count(inlier_count),
        .is_inlier(is_inlier)
    );

    task check_point;
		input signed [39:0] test_x;
      input expected;
      begin
			x = test_x;
         #10;

         if (is_inlier !== expected) 
				begin
					errors = errors + 1;
					$display("FALHA x_escalado=%0d esperado=%b obtido=%b", x, expected, is_inlier);
				end 
			else 
				begin
					$display("OK x_escalado=%0d is_inlier=%b", x, is_inlier);
            end
			
			point_index = point_index + 12'd1;
       end
		  
    endtask
	 
	 task check_result;
		 input [11:0] index;
		 input expected;
		 begin
			  read_index = index;
			  @(posedge clk);
			  @(negedge clk);

			  if (read_inlier !== expected) begin
					errors = errors + 1;
					$display("FALHA indice=%0d esperado=%b lido=%b",
								index, expected, read_inlier);
			  end else begin
					$display("OK indice=%0d lido=%b", index, read_inlier);
			  end
		 end
	 endtask

    initial begin
		errors = 0;
		point_index = 12'd0; 
		
		clear = 1'b1;
		point_valid = 1'b0;
		@(negedge clk);
		clear = 1'b0;
		point_valid = 1'b1;

      // Para representar um valor, multiplique por 2^24.
      a =  40'sd8388608;     //  0.5
      b = -40'sd16777216;    // -1.0
      c =  40'sd176160768;   // 10.5
      y =  16'sd2;
      threshold = 40'sd16777216;  // 1.0

      // Para y = 2, a parábola prevê x = 10.5.
      check_point(40'sd176160768, 1'b1);  // x = 10.5, dx =  0.0
      check_point(40'sd167772160, 1'b1);  // x = 10.0, dx = -0.5
      check_point(40'sd184549376, 1'b1);  // x = 11.0, dx = +0.5
      check_point(40'sd159383552, 1'b0);  // x =  9.5, dx = -1.0
      check_point(40'sd192937984, 1'b0);  // x = 11.5, dx = +1.0

		point_valid = 1'b0;
		
		check_result(12'd0, 1'b1);
		check_result(12'd1, 1'b1);
		check_result(12'd2, 1'b1);
		check_result(12'd3, 1'b0);
		check_result(12'd4, 1'b0);

		if (inlier_count !== 32'd3)
			 errors = errors + 1;

		$display("Total de inliers: %0d (esperado: 3)", inlier_count);
		
		// Começa uma nova avaliação.
		clear = 1'b1;
		@(posedge clk);
		@(negedge clk);
		clear = 1'b0;

		if (inlier_count !== 32'd0) begin
			 errors = errors + 1;
			 $display("FALHA: clear nao zerou a contagem");
		end

		point_index = 12'd0;
		point_valid = 1'b1;

		check_point(40'sd159383552, 1'b0);  // índice 0: rejeitado
		check_point(40'sd176160768, 1'b1);  // índice 1: aceito
		check_point(40'sd192937984, 1'b0);  // índice 2: rejeitado

		point_valid = 1'b0;
		
		check_result(12'd0, 1'b0);
		check_result(12'd1, 1'b1);
		check_result(12'd2, 1'b0);

		if (inlier_count !== 32'd1)
			 errors = errors + 1;

		$display("Segunda avaliacao:");
		$display("Total de inliers: %0d (esperado: 1)", inlier_count);
		
		
      $display("Total GERAL de falhas: %0d", errors);
      $stop;
    end
endmodule