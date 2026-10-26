#ifndef NIOS_MAILBOX_H
#define NIOS_MAILBOX_H

/* Layout da MBOX em palavras de 32 bits
   tools/ismce_run.py faz o parse destes #define, entao mantenha o formato
   "#define MBOX_NOME valor" */
// Cada double ocupa duas palavras com os bits IEEE 754, palavra baixa primeiro

#define MBOX_MAGIC_VALUE 0x5253434EU // "RSCN": Nios pronto para comandos
#define MBOX_VERSION_VALUE 1U
#define MBOX_COMMAND_RUN 1U
#define MBOX_STATUS_RUNNING 0xFFFFFFFFU
#define MBOX_STATUS_BAD_INPUT 0x100U // dimensoes nulas ou maiores que IMG

// Controle
#define MBOX_MAGIC 0
#define MBOX_VERSION 1
#define MBOX_COMMAND 2       // PC escreve 1 e o Nios zera ao terminar
#define MBOX_SEQUENCE 3      // execucoes concluidas
#define MBOX_HEARTBEAT 4     // incrementado enquanto o Nios espera
#define MBOX_IMG_CAPACITY 5  // bytes disponiveis na memoria IMG

// Entradas (escritas pelo PC antes do comando)
#define MBOX_WIDTH 8
#define MBOX_HEIGHT 9
#define MBOX_ITERATIONS 10
#define MBOX_THRESHOLD_MILLI 11 // threshold em milesimos de pixel
#define MBOX_MIN_INLIERS 12
#define MBOX_SEED 13
#define MBOX_THICKNESS 14

// Saidas (escritas pelo Nios antes de zerar o comando)
#define MBOX_STATUS 16 // LaneStatus ou MBOX_STATUS_*
#define MBOX_FOUND 17
#define MBOX_POINTS 18
#define MBOX_INLIERS 19
#define MBOX_A 20
#define MBOX_B 22
#define MBOX_C 24
#define MBOX_MSE 26
#define MBOX_MASK_HASH 28 // FNV-1a da mascara final
#define MBOX_RGB_HASH 29  // FNV-1a do RGB recebido (confere a transferencia)
#define MBOX_CYCLES 32    // pares baixo/alto: total e secoes 1..7

#define MBOX_WORDS 48

#endif
