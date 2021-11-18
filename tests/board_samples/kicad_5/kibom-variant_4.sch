EESchema Schematic File Version 4
EELAYER 30 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title ""
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L kibom-variant_4-rescue:WC1602A-Display_Character DS1001
U 1 1 61958928
P 2875 2425
F 0 "DS1001" H 2875 3402 50  0000 C CNN
F 1 "LCD16x02" H 2875 3313 50  0000 C CNN
F 2 "kibom-variant_4:LCD_16x02_Dual" H 2875 1525 50  0001 C CIN
F 3 "" H 3575 2425 50  0001 C CNN
F 4 "WH1602B-TMI-JT#" H 2875 2425 50  0001 C CNN "kicost.topvariant:Value"
F 5 "ERM1602DNS-2.1" H 2875 2425 50  0001 C CNN "kicost.leftvariant:Value"
F 6 "209863" H 2875 2425 50  0001 C CNN "kicost.topvariant:sos#"
F 7 "" H 2875 2425 50  0001 C CNN "dnp"
F 8 "Test for 3D Model variants, also tests dnp and not fields that are not defined otherwise." H 2875 2425 50  0001 C CNN "Comment"
F 9 "WH1602B-TMI-JT#" H 2875 2425 50  0001 C CNN "kicost.topvariant:manf#"
F 10 "ERM1602DNS-2.1" H 2875 2425 50  0001 C CNN "kicost.leftvariant:manf#"
	1    2875 2425
	1    0    0    -1  
$EndComp
$Comp
L Connector:Conn_01x12_Female J1
U 1 1 6196B4C4
P 5350 2450
F 0 "J1" H 5378 2426 50  0000 L CNN
F 1 "Conn_01x12_Female" H 5378 2335 50  0000 L CNN
F 2 "Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical" H 5350 2450 50  0001 C CNN
F 3 "~" H 5350 2450 50  0001 C CNN
	1    5350 2450
	1    0    0    -1  
$EndComp
$EndSCHEMATC
