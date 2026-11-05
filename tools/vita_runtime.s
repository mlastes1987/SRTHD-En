.syntax unified
.arch armv7-a
.fpu neon
.thumb
.section .text
.global measure_class, measure_default, measure_plain, draw_bearing, draw_advance
.global page_init, page_update, page_render, split_buffer, page_tick, page_select
.global faction_ally_big, faction_enemy_small, faction_ally_small, faction_enemy_big

.macro save
    push.w {r0-r4, r12, lr}
    mrs r4, apsr
    push {r4}
    vpush {s4-s7}
.endm

.macro save_arm
    push.w {r0-r4,r12,lr}
    mrs r4,apsr
    push {r4}
.endm
.macro restore_arm
    pop {r4}
    msr apsr_nzcvq,r4
    pop.w {r0-r4,r12,lr}
.endm
.macro restore
    vpop {s4-s7}
    pop {r4}
    msr apsr_nzcvq, r4
    pop.w {r0-r4, r12, lr}
.endm

measure_class:
    vmov.f32 s3, s1
    save
    vldr s7, [r11, #0x48]
    bl measure_worker
    restore
    b.w return_measure_class
measure_default:
    vmov.f32 s3, s2
    save
    vldr s7, [r11, #0x38]
    bl measure_worker
    restore
    b.w return_measure_default
measure_plain:
    vldr s3, [r11, #0x1c]
    save
    vldr s7, [r11, #0x14]
    bl measure_worker
    restore
    b.w return_measure_plain

measure_worker:
    push {r4,lr}
    movw r0, #0x8140
    cmp.w r2, #0x8200
    blt 1f
    add.w r0, r0, #0x40
1:  sub.w r0, r2, r0
    bl glyph_metric
    cbz r1, 2f
    bl pixel_advance
    vmov.f32 s3,s4
2:  pop {r4,pc}

draw_bearing:
    vmov.f32 s0,s18
    save
    mov r0,r8
    bl glyph_metric
    cbz r1, 1f
    ubfx r0,r1,#9,#5
    vmov s4,r0
    vcvt.f32.u32 s4,s4,#5
    vmul.f32 s4,s4,s19
    vsub.f32 s0,s0,s4
1:  restore
    b.w return_draw_bearing

draw_advance:
    save
    mov r0,r8
    bl glyph_metric
    cbz r1, 1f
    vmov.f32 s7,s19
    bl pixel_advance
    vadd.f32 s18,s18,s4
    b 2f
1:  vadd.f32 s18,s18,s21
2:  restore
    b.w return_draw_advance

glyph_metric:
    movs r1,#0
    cmp.w r0,#282
    bhi 1f
    adr.w r1,font_metrics
    ldrh.w r1,[r1,r0,lsl #1]
1:  bx lr

pixel_advance:
    ubfx r0,r1,#0,#9
    cmp r0,#102
    beq 2f
    vmov s4,r0
    vcvt.f32.u32 s4,s4,#8
    b 3f
2:  vldr s4,space_advance
3:
    vmul.f32 s4,s4,s7
    tst.w r1,#0x4000
    beq 1f
    vmov.f32 s5,#1.0
    vsub.f32 s4,s4,s5
1:  vcvt.s32.f32 s4,s4
    vcvt.f32.s32 s4,s4
    bx lr

page_init:
    save_arm
    ldr r0,quote_buffers
    bl split_buffer
    ldr r0,quote_buffers
    adds r0,#121
    bl split_buffer
    ldr r0,quote_pointer
    movs r1,#0
    str r1,[r0]
    restore_arm
    movw r0,#0xcdcc
    b.w return_page_init

split_buffer:
.type split_buffer,%function
    movs r1,#0
    strb.w r1,[r0,#104]
    strb.w r1,[r0,#105]
    movs r2,#0
1:  ldrb r3,[r0,r2]
    cbz r3,3f
    cmp r3,#10
    bne 2f
    adds r1,#1
    cmp r1,#2
    bne 2f
    movs r3,#0
    strb r3,[r0,r2]
    adds r2,#1
    strb.w r2,[r0,#104]
    bx lr
2:  adds r2,#1
    cmp r2,#104
    blt 1b
3:  bx lr

page_update:
    save_arm
    // The native delta is in LR before the hook's BLs.
    ldr r3,[sp,#28]
    bl page_tick
    cbz r0,1f
    restore_arm
    movs r0,#0
    b.w return_page_hold
1:  restore_arm
    movw r0,#0xd18c
    b.w return_page_update

page_tick:
.type page_tick,%function
    push {r3,lr}
    bl page_select
    pop {r3,lr}
    cbz r2,3f
    ldrb.w r4,[r1,#105]
    cmp r4,#240
    bge 3f
    add r4,r3
    cmp r4,#240
    ble 1f
    movs r4,#240
1:  strb.w r4,[r1,#105]
    cmp r4,#120
    blt 2f
    add r2,r1
    ldr r0,quote_pointer
    str r2,[r0]
2:  movs r0,#1
    bx lr
3:  movs r0,#0
    bx lr

page_select:
.type page_select,%function
    ldr r0,quote_pointer
    ldr r0,[r0]
    ldr r1,quote_buffers
    movs r4,#2
1:  ldrb.w r2,[r1,#104]
    cbz r2,2f
    cmp r0,r1
    beq 3f
    add.w r12,r1,r2
    cmp r0,r12
    beq 3f
2:  adds r1,#121
    subs r4,#1
    bne 1b
    movs r2,#0
3:  bx lr

page_render:
    save_arm
    bl page_select
    cbz r2,1f
    ldrb.w r3,[r1,#105]
    cmp r3,#120
    blt 1f
    add r2,r1
    ldr r0,quote_pointer
    str r2,[r0]
1:  restore_arm
    movw r5,#0xcae0
    b.w return_page_render

faction_ally_big:
    vldr s0,faction_positions
    b.w return_faction_ally_big
faction_enemy_small:
    vldr s0,faction_positions+4
    b.w return_faction_enemy_small
faction_ally_small:
    vldr s0,faction_positions+8
    b.w return_faction_ally_small
faction_enemy_big:
    vldr s0,faction_positions+12
    b.w return_faction_enemy_big

.balign 4
faction_positions:
    .incbin "work/vita/faction_positions.bin"
quote_buffers:
    .word 0x8125cdf4
quote_pointer:
    .word 0x8125d0cc
space_advance:
    .float 0.4
font_metrics:
    .incbin "work/vita/font_metrics.bin"
