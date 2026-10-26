# Cria o projeto Quartus da P1 para a DE2-115
# Uso: quartus_sh -t ransac_nios_project.tcl, depois de gerar o Qsys
# Pinos e padroes de I/O conferidos com o DE2_115.qsf do University Program e
# com o manual da placa
# LEDG e KEY ficam nos bancos 5/6, cuja tensao depende do jumper JP7 (padrao
# 2,5 V), e a SDRAM usa 3,3 V

package require ::quartus::project

project_new ransac_nios -revision ransac_nios -overwrite

set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name DEVICE EP4CE115F29C7
set_global_assignment -name TOP_LEVEL_ENTITY ransac_nios_top
set_global_assignment -name VERILOG_FILE ransac_nios_top.v
set_global_assignment -name QIP_FILE ransac_nios/synthesis/ransac_nios.qip
set_global_assignment -name SDC_FILE ransac_nios.sdc
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name NUM_PARALLEL_PROCESSORS ALL
set_global_assignment -name RESERVE_ALL_UNUSED_PINS_WEAK_PULLUP "AS INPUT TRI-STATED"
set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name STRATIX_DEVICE_IO_STANDARD "3.3-V LVTTL"

proc pin {name location {standard "3.3-V LVTTL"}} {
    set_location_assignment $location -to $name
    set_instance_assignment -name IO_STANDARD $standard -to $name
}
proc pins {name locations {standard "3.3-V LVTTL"}} {
    set index 0
    foreach location $locations {
        pin "${name}\[$index\]" $location $standard
        incr index
    }
}

pin CLOCK_50 PIN_Y2
pins KEY {PIN_M23 PIN_M21 PIN_N21 PIN_R24} "2.5 V"
pins LEDG {PIN_E21 PIN_E22 PIN_E25 PIN_E24 PIN_H21 PIN_G20 PIN_G22 PIN_G21 PIN_F17} "2.5 V"

pins DRAM_ADDR {PIN_R6 PIN_V8 PIN_U8 PIN_P1 PIN_V5 PIN_W8 PIN_W7 PIN_AA7 PIN_Y5
                PIN_Y6 PIN_R5 PIN_AA5 PIN_Y7}
pins DRAM_BA {PIN_U7 PIN_R4}
pin DRAM_CAS_N PIN_V7
pin DRAM_CKE PIN_AA6
pin DRAM_CLK PIN_AE5
pin DRAM_CS_N PIN_T4
pins DRAM_DQ {PIN_W3 PIN_W2 PIN_V4 PIN_W1 PIN_V3 PIN_V2 PIN_V1 PIN_U3
              PIN_Y3 PIN_Y4 PIN_AB1 PIN_AA3 PIN_AB2 PIN_AC1 PIN_AB3 PIN_AC2
              PIN_M8 PIN_L8 PIN_P2 PIN_N3 PIN_N4 PIN_M4 PIN_M7 PIN_L7
              PIN_U5 PIN_R7 PIN_R1 PIN_R2 PIN_R3 PIN_T3 PIN_U4 PIN_U1}
pins DRAM_DQM {PIN_U2 PIN_W4 PIN_K8 PIN_N8}
pin DRAM_RAS_N PIN_U6
pin DRAM_WE_N PIN_V6

project_close
