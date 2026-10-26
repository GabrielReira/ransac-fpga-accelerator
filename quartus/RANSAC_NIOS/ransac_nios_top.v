// Top-level da P1 (somente software) para a DE2-115
// KEY[0] e o reset ativo baixo
// LEDG[7:0] vem do PIO do Nios e LEDG[8] indica PLL travado
module ransac_nios_top (
    input  wire        CLOCK_50,
    input  wire [3:0]  KEY,
    output wire [8:0]  LEDG,

    output wire [12:0] DRAM_ADDR,
    output wire [1:0]  DRAM_BA,
    output wire        DRAM_CAS_N,
    output wire        DRAM_CKE,
    output wire        DRAM_CLK,
    output wire        DRAM_CS_N,
    inout  wire [31:0] DRAM_DQ,
    output wire [3:0]  DRAM_DQM,
    output wire        DRAM_RAS_N,
    output wire        DRAM_WE_N
);

    wire [4:0] pll_clk;
    wire       pll_locked;
    wire       sys_clk = pll_clk[0];

    // c0 alimenta o sistema
    // c1 sai 3 ns adiantado para o DRAM_CLK e compensa o atraso de saida
    // (valor padrao nos exemplos da DE2-115)
    altpll #(
        .intended_device_family  ("Cyclone IV E"),
        .lpm_type                ("altpll"),
        .operation_mode          ("NORMAL"),
        .compensate_clock        ("CLK0"),
        .inclk0_input_frequency  (20000),
        .clk0_multiply_by        (1),
        .clk0_divide_by          (1),
        .clk0_duty_cycle         (50),
        .clk0_phase_shift        ("0"),
        .clk1_multiply_by        (1),
        .clk1_divide_by          (1),
        .clk1_duty_cycle         (50),
        .clk1_phase_shift        ("-3000"),
        .port_clk0               ("PORT_USED"),
        .port_clk1               ("PORT_USED"),
        .port_locked             ("PORT_USED"),
        .port_areset             ("PORT_USED"),
        .width_clock             (5)
    ) sys_pll (
        .inclk  ({1'b0, CLOCK_50}),
        .areset (1'b0),
        .clk    (pll_clk),
        .locked (pll_locked)
    );

    assign DRAM_CLK = pll_clk[1];
    assign LEDG[8]  = pll_locked;

    ransac_nios u_system (
        .clk_clk       (sys_clk),
        .reset_reset_n (KEY[0] & pll_locked),
        .led_export    (LEDG[7:0]),
        .sdram_addr    (DRAM_ADDR),
        .sdram_ba      (DRAM_BA),
        .sdram_cas_n   (DRAM_CAS_N),
        .sdram_cke     (DRAM_CKE),
        .sdram_cs_n    (DRAM_CS_N),
        .sdram_dq      (DRAM_DQ),
        .sdram_dqm     (DRAM_DQM),
        .sdram_ras_n   (DRAM_RAS_N),
        .sdram_we_n    (DRAM_WE_N)
    );

endmodule
