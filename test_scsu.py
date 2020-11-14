#coding:utf-8

import sys
import scsu

# ASCII
byte_array = bytearray([0x4E, 0x61, 0x75, 0x74, 0x69, 0x63, 0x61, 0x6C]) # 'Nautical', 8 characters
# This should be converted to:
#     [0x4E, 0x61, 0x75, 0x74, 0x69, 0x63, 0x61, 0x6C]
output_array, counter, char_counter = scsu.decode(byte_array, 5)
print('ASCII:', output_array.decode("utf-8", "ignore"), ', bytes:', 
      counter, ', characters:' ,char_counter)
#print(output_array, '\n')
for i in output_array:
    print(hex(i), ' ', sep='', end='')
print('\n')

# Japanese
byte_array = bytearray(
    [0x08, 0x00, 0x1B, 0x4C, 0xEA, 0x16, 0xCA, 0xD3, 0x94, 0x0F, 0x53, 0xEF, 0x61, 
     0x1B, 0xE5, 0x84, 0xC4, 0x0F, 0x53, 0xEF, 0x61, 0x1B, 0xE5, 0x84, 0xC4, 0x16,
     0xCA, 0xD3, 0x94, 0x08, 0x02]) # '　♪リンゴ可愛いや可愛いやリンゴ。', 17 characters
# This should be converted to:
#     [0xe38080 0xe299aa 0xe383aa 0xe383b3 0xe382b4 0xe58faf 0xe6849b 0xe38184 
#      0xe38284 0xe58faf 0xe6849b 0xe38184 0xe38284 0xe383aa 0xe383b3 0xe382b4 
#      0xe38082]
output_array, counter, char_counter = scsu.decode(byte_array, 9)
print('Japanese:', output_array.decode("utf-8", "ignore"), ', bytes:', 
      counter, ', characters:' ,char_counter)
#print(output_array, '\n')
for i in output_array:
    print(hex(i), ' ', sep='', end='')
print('\n')

# German
byte_array = bytearray([0xD6, 0x6C, 0x20, 0x66, 0x6C, 0x69, 0x65, 0xDF, 0x74]) # 'Öl fließt', 9 characters
# This should be converted to:
#     [0xc396 0x6c 0x20 0x66 0x6c 0x69 0x65 0xc39f 0x74]
output_array, counter, char_counter = scsu.decode(byte_array, 4)
print('German:', output_array.decode("utf-8", "ignore"), ', bytes:', \
      counter, ', characters: ' ,char_counter)
#print(output_array, '\n')
for i in output_array:
    print(hex(i), ' ', sep='', end='')
print('\n')

# Russian
byte_array = bytearray([0x12, 0x9C, 0xBE, 0xC1, 0xBA, 0xB2, 0xB0]) # 'Москва', 6 characters
# This should be converted to:
#     [0xd09c 0xd0be 0xd181 0xd0ba 0xd0b2 0xd0b0]
output_array, counter, char_counter = scsu.decode(byte_array, 3)
print('Russian:', output_array.decode("utf-8", "ignore"), ', bytes:', \
      counter, ', characters: ' ,char_counter)
#print(output_array, '\n')
for i in output_array:
    print(hex(i), ' ', sep='', end='')
print('\n')

# All Features
byte_array = bytearray(
    [0x41, 0xDF, 0x12, 0x81, 0x03, 0x5F, 0x10, 0xDF, 0x1B, 0x03, 0xDF, 0x1C, 0x88, 0x80, 0x0B, 0xBF, 0xFF, 0xFF, 
     0x0D, 0x0A, 
     0x41, 0x10, 0xDF, 0x12, 0x81, 0x03, 0x5F, 0x10, 0xDF, 0x13, 0xDF, 0x14, 0x80, 0x15, 0xFF]) 
#'AßЁşßǟ\xEF8080\xF48FBFBF\0D\0AAßЁşßǟ\xEF8080\xF48FBFBF', 18 characters
# This should be converted to:
# codepoint    [0x41 0xdf 0x401 0x15f 0xdf 0x1df 0xf000 0x10ffff 0xd 0xa 
#               0x41 0xdf 0x401 0x15f 0xdf 0x1df 0xf000 0x10ffff]
# utf-8        [0x41 0xc39f 0xd081 0xc59f 0xc39f 0xc79f 0xef8080 0xf48fbfbf 0xd 0xa 
#               0x41 0xc39f 0xd081 0xc59f 0xc39f 0xc79f 0xef8080 0xf48fbfbf ]
output_array, counter, char_counter = scsu.decode(byte_array, 10)
print('All Features:', output_array.decode("utf-8", "ignore"), ', bytes:', \
      counter, ', characters:' ,char_counter)
#print(output_array, '\n')
print('Codepoint: ', end='')
for i in output_array.decode():
    print(hex(ord(i)), ' ', sep='', end='')
print('\n')
print('utf-8: ', end='')
for i in output_array:
    print(hex(i), ' ', sep='', end='')
print('\n')

