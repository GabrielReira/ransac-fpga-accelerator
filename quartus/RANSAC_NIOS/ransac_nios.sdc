create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]

derive_pll_clocks
derive_clock_uncertainty

# KEY e LEDG sao assincronos e lentos
set_false_path -from [get_ports {KEY[*]}]
set_false_path -to [get_ports {LEDG[*]}]

# A janela da SDRAM vem do DRAM_CLK adiantado 3 ns a 50 MHz, como nos
# exemplos da Terasic
