module de2_115_top (
    input wire CLOCK_50,
    input wire KEY0
);

    nios_consensus system_nios (
        .clk_clk       (CLOCK_50),
        .reset_reset_n (KEY0)
    );

endmodule