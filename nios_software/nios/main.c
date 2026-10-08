#include "entry.h"

/* Preencha nios_rgb e escreva 1 em nios_request para processar um frame.
   A integracao UART/JTAG deve garantir visibilidade dos buffers e da flag
   (regiao sem cache ou manutencao de cache no BSP). */
volatile uint32_t nios_request;
volatile uint32_t nios_status;

int main(void)
{
    while (1) {
        if (nios_request == 1) {
            nios_status = (uint32_t)nios_process_rgb();
            nios_request = 0; /* Outputs prontos; consulte nios_status e found. */
        }
    }
}
