# Transporte JTAG da estrutura de teste ISMCE, chamado por tools/ismce_run.py
# Uso: quartus_stp -t ismce_run.tcl <img_words> <mbox_in> <mbox_out>
#                  <mbox_words> <magic> <command_word> <timeout_s> [cable]
#   img_words: uma palavra hex de 32 bits por linha, a partir do endereco 0
#              (arquivo vazio: mantem a imagem ja carregada em IMG)
#   mbox_in:   linhas "<indice> <valor hex>" com as entradas da MBOX
#   mbox_out:  recebe as mbox_words primeiras palavras da MBOX, uma por linha

package require ::quartus::jtag
package require ::quartus::insystem_memory_edit

lassign $quartus(args) img_file mbox_in_file mbox_out_file mbox_words magic \
    command_word timeout_s cable

proc fail {message} {
    puts stderr "ERRO: $message"
    catch end_memory_edit
    exit 1
}

if {$cable eq ""} {
    set hardware_names [get_hardware_names]
    if {[llength $hardware_names] == 0} {
        fail "nenhum cabo JTAG encontrado (verifique jtagconfig)"
    }
    set cable [lindex $hardware_names 0]
}
set device ""
foreach name [get_device_names -hardware_name $cable] {
    if {[string match "*EP4CE115*" $name]} {
        set device $name
    }
}
if {$device eq ""} {
    fail "EP4CE115 nao encontrado em $cable"
}

set instances [dict create]
foreach instance [get_editable_mem_instances -hardware_name $cable -device_name $device] {
    dict set instances [lindex $instance 5] [lindex $instance 0]
}
foreach id {MBOX IMG} {
    if {![dict exists $instances $id]} {
        fail "memoria $id nao encontrada; o .sof gravado e o da P1 com ISMCE?"
    }
}
set mbox [dict get $instances MBOX]
set img [dict get $instances IMG]

# -content espera o endereco mais alto primeiro e sem separadores, dai o lreverse
proc write_words {index start words} {
    set chunk 1024
    for {set offset 0} {$offset < [llength $words]} {incr offset $chunk} {
        set part [lrange $words $offset [expr {$offset + $chunk - 1}]]
        write_content_to_memory -instance_index $index \
            -start_address [expr {$start + $offset}] -word_count [llength $part] \
            -content [join [lreverse $part] ""] -content_in_hex -timeout 60000
    }
}
#a leitura vem na mesma ordem: a palavra de start fica no fim da string
proc read_words {index start count} {
    set content [read_content_from_memory -instance_index $index \
        -start_address $start -word_count $count -content_in_hex]
    set words {}
    for {set i 0} {$i < $count} {incr i} {
        set position [expr {8 * ($count - 1 - $i)}]
        lappend words [string range $content $position [expr {$position + 7}]]
    }
    return $words
}
proc read_word {index address} {
    return [expr {"0x[lindex [read_words $index $address 1] 0]"}]
}

begin_memory_edit -hardware_name $cable -device_name $device

if {[read_word $mbox 0] != $magic} {
    fail "Nios nao esta pronto (carregue ransac_ismce.elf com nios2-download -g)"
}

set handle [open $img_file r]
set img_words [split [string trim [read $handle]] "\n"]
close $handle
if {[llength $img_words] > 0 && [lindex $img_words 0] ne ""} {
    set started [clock milliseconds]
    write_words $img 0 $img_words
    puts "IMG: [llength $img_words] palavras em [expr {[clock milliseconds] - $started}] ms"
}

set handle [open $mbox_in_file r]
foreach line [split [string trim [read $handle]] "\n"] {
    lassign $line address value
    write_words $mbox $address [list $value]
}
close $handle

# Comando por ultimo e sozinho, para o Nios nunca ver entradas pela metade
write_words $mbox 2 [list [format %08X $command_word]]
set started [clock milliseconds]
set deadline [expr {$started + 1000 * $timeout_s}]
while {[read_word $mbox 2] != 0} {
    if {[clock milliseconds] > $deadline} {
        fail "timeout de $timeout_s s esperando o Nios"
    }
    after 100
}
puts "Nios: concluido em ~[expr {[clock milliseconds] - $started}] ms (inclui polling JTAG)"

set handle [open $mbox_out_file w]
puts $handle [join [read_words $mbox 0 $mbox_words] "\n"]
close $handle
end_memory_edit
