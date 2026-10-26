# Sistema Platform Designer da P1 (somente software)
# Uso: qsys-script --script=ransac_nios_qsys.tcl [--cmd="set cpu_impl Fast"]
#
# Tiny (/e) e o padrao por dispensar licenca
# Fast (/f) sem licenca gera um .sof OpenCore Plus que so roda com o cabo JTAG conectado

package require -exact qsys 16.1

if {![info exists cpu_impl]} {
    set cpu_impl Tiny
}

create_system ransac_nios
set_project_property DEVICE_FAMILY {Cyclone IV E}
set_project_property DEVICE {EP4CE115F29C7}

# 50 MHz do c0 do PLL no top-level, mesma frequencia do CLOCK_50
add_instance clk_0 clock_source
set_instance_parameter_value clk_0 clockFrequency 50000000
set_instance_parameter_value clk_0 clockFrequencyKnown true
set_instance_parameter_value clk_0 resetSynchronousEdges DEASSERT

add_instance cpu altera_nios2_gen2
set_instance_parameter_value cpu impl $cpu_impl
set_instance_parameter_value cpu resetSlave sdram.s1
set_instance_parameter_value cpu resetOffset 0x0
set_instance_parameter_value cpu exceptionSlave sdram.s1
set_instance_parameter_value cpu exceptionOffset 0x20

# 2x IS42S16320D em paralelo: 128 MB com barramento de 32 bits
add_instance sdram altera_avalon_new_sdram_controller
set_instance_parameter_value sdram dataWidth 32
set_instance_parameter_value sdram numberOfChipSelects 1
set_instance_parameter_value sdram numberOfBanks 4
set_instance_parameter_value sdram rowWidth 13
set_instance_parameter_value sdram columnWidth 10
set_instance_parameter_value sdram casLatency 3
set_instance_parameter_value sdram initRefreshCommands 2
set_instance_parameter_value sdram refreshPeriod 7.8125
set_instance_parameter_value sdram powerUpDelay 100.0
set_instance_parameter_value sdram TRFC 70.0
set_instance_parameter_value sdram TRP 20.0
set_instance_parameter_value sdram TRCD 20.0
set_instance_parameter_value sdram TAC 5.5
set_instance_parameter_value sdram TWR 14.0
set_instance_parameter_value sdram TMRD 3

add_instance jtag_uart altera_avalon_jtag_uart

# Timer de sistema do HAL (usleep, alt_nticks)
add_instance sys_timer altera_avalon_timer
set_instance_parameter_value sys_timer period 1
set_instance_parameter_value sys_timer periodUnits MSEC

#secoes 1..7 seguem LaneProfileSection em nios_software/include/lane_profile.h
add_instance perf_counter altera_avalon_performance_counter
set_instance_parameter_value perf_counter numberOfSections 7

add_instance sysid altera_avalon_sysid_qsys
set_instance_parameter_value sysid id 0x20260201

# Memorias on-chip expostas ao In-System Memory Content Editor via JTAG
# MBOX: comandos e resultados, layout em nios_software/nios/mailbox.h
# IMG: frame RGB888 de entrada, 192 KiB cabem ate 320x200
# tools/ismce_run.tcl localiza as memorias pelo instanceID
proc add_ismce_memory {name id bytes} {
    add_instance $name altera_avalon_onchip_memory2
    set_instance_parameter_value $name memorySize $bytes
    set_instance_parameter_value $name dataWidth 32
    set_instance_parameter_value $name initMemContent false
    set_instance_parameter_value $name allowInSystemMemoryContentEditor true
    set_instance_parameter_value $name instanceID $id
}
add_ismce_memory mailbox MBOX 1024
add_ismce_memory img_buf IMG 196608

add_instance led_pio altera_avalon_pio
set_instance_parameter_value led_pio width 8
set_instance_parameter_value led_pio direction Output

foreach instance {cpu sdram jtag_uart sys_timer perf_counter sysid led_pio} {
    add_connection clk_0.clk $instance.clk
    add_connection clk_0.clk_reset $instance.reset
    add_connection cpu.debug_reset_request $instance.reset
}
foreach instance {mailbox img_buf} {
    add_connection clk_0.clk $instance.clk1
    add_connection clk_0.clk_reset $instance.reset1
    add_connection cpu.debug_reset_request $instance.reset1
}

# A SDRAM ocupa 0x0000_0000-0x07FF_FFFF e os perifericos ficam logo acima
proc connect_master {master slave base} {
    add_connection $master $slave
    set_connection_parameter_value $master/$slave baseAddress $base
}
foreach master {cpu.instruction_master cpu.data_master} {
    connect_master $master sdram.s1 0x00000000
    connect_master $master cpu.debug_mem_slave 0x08000000
}
connect_master cpu.data_master jtag_uart.avalon_jtag_slave 0x08001000
connect_master cpu.data_master sys_timer.s1 0x08001020
connect_master cpu.data_master sysid.control_slave 0x08001040
connect_master cpu.data_master led_pio.s1 0x08001050
connect_master cpu.data_master perf_counter.control_slave 0x08001080
connect_master cpu.data_master mailbox.s1 0x08002000
connect_master cpu.data_master img_buf.s1 0x08040000

add_connection cpu.irq jtag_uart.irq
set_connection_parameter_value cpu.irq/jtag_uart.irq irqNumber 0
add_connection cpu.irq sys_timer.irq
set_connection_parameter_value cpu.irq/sys_timer.irq irqNumber 1

add_interface clk clock sink
set_interface_property clk EXPORT_OF clk_0.clk_in
add_interface reset reset sink
set_interface_property reset EXPORT_OF clk_0.clk_in_reset
add_interface sdram conduit end
set_interface_property sdram EXPORT_OF sdram.wire
add_interface led conduit end
set_interface_property led EXPORT_OF led_pio.external_connection

save_system ransac_nios.qsys
