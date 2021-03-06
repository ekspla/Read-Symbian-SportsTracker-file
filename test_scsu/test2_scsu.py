﻿#coding:utf-8
# Another test code of scsu decoder, scsu.py.
import scsu

# Define a list of example sentences.
# Example SCSU encoded bytes were obtained by the following encoder. 
# https://github.com/normano/scsu
#
example_sentences = [
    ('Mandarin', '統一碼是電腦科學領域裡的一項業界標準。',
        (
            b'\x0f\x7d\x71\x4e\x00\x78\xbc\x66\x2f\x96\xfb\x81\x66\x79\xd1\x5b\x78\x98\x18\x57\xdf\x88\xe1\x76\x84\x4e'
            b'\x00\x98\x05\x69\x6d\x75\x4c\x6a\x19\x6e\x96\x30\x02')),
    ('Spanish', 'Unicode es un estándar de codificación de caracteres diseñado para facilitar el tratamiento '
        'informático, transmisión y visualización de textos de múltiples lenguajes y disciplinas técnicas,'
        'además de textos clásicos de lenguas muertas.',
        (
            b'Unicode es un est\xe1ndar de codificaci\xf3n de caracteres dise\xf1ado para facilitar '
            b'el tratamiento inform\xe1tico, transmisi\xf3n y visualizaci\xf3n de textos de m\xfaltiples lenguajes '
            b'y disciplinas t\xe9cnicas,adem\xe1s de textos cl\xe1sicos de lenguas muertas.')),
    ('English', 'Unicode is a computing industry standard for the consistent encoding, representation, and handling '
        'of text expressed in most of the world\'s writing systems.',
        (
            b"Unicode is a computing industry standard for the consistent encoding, representation, and handling of "
            b"text expressed in most of the world\'s writing systems.")),
    ('Hindi', 'यूनिकोड प्रत्येक अक्षर के लिए एक विशेष संख्या प्रदान करता है, चाहे कोई भी कम्प्यूटर प्लेटफॉर्म, '
        'प्रोग्राम अथवा कोई भी भाषा हो।',
        (
            b'\x14\xaf\xc2\xa8\xbf\x95\xcb\xa1 \xaa\xcd\xb0\xa4\xcd\xaf\xc7\x95 \x85\x95\xcd\xb7\xb0 \x95\xc7 \xb2\xbf'
            b'\x8f \x8f\x95 \xb5\xbf\xb6\xc7\xb7 \xb8\x82\x96\xcd\xaf\xbe \xaa\xcd\xb0\xa6\xbe\xa8 \x95\xb0\xa4\xbe '
            b'\xb9\xc8, \x9a\xbe\xb9\xc7 \x95\xcb\x88 \xad\xc0 \x95\xae\xcd\xaa\xcd\xaf\xc2\x9f\xb0 \xaa\xcd\xb2\xc7'
            b'\x9f\xab\xc9\xb0\xcd\xae, \xaa\xcd\xb0\xcb\x97\xcd\xb0\xbe\xae \x85\xa5\xb5\xbe \x95\xcb\x88 \xad\xc0 '
            b'\xad\xbe\xb7\xbe \xb9\xcb\xe4')),
    ('Arabic', 'في علم الحاسوب، الترميز الموحد (يونيكود أو يُونِكُود) معيار يمكن الحواسيب من تمثيل النصوص المكتوبة '
        'بأغلب نظم الكتابة ومعالجتها، بصورة متناسقة.',
        (
            b'\x13\xc1\xca \xb9\xc4\xc5 \xa7\xc4\xad\xa7\xb3\xc8\xa8\x8c \xa7\xc4\xaa\xb1\xc5\xca\xb2 \xa7\xc4\xc5\xc8'
            b'\xad\xaf (\xca\xc8\xc6\xca\xc3\xc8\xaf \xa3\xc8 \xca\xcf\xc8\xc6\xd0\xc3\xcf\xc8\xaf) \xc5\xb9\xca\xa7'
            b'\xb1 \xca\xc5\xc3\xc6 \xa7\xc4\xad\xc8\xa7\xb3\xca\xa8 \xc5\xc6 \xaa\xc5\xab\xca\xc4 \xa7\xc4\xc6\xb5\xc8'
            b'\xb5 \xa7\xc4\xc5\xc3\xaa\xc8\xa8\xa9 \xa8\xa3\xba\xc4\xa8 \xc6\xb8\xc5 \xa7\xc4\xc3\xaa\xa7\xa8\xa9 \xc8'
            b'\xc5\xb9\xa7\xc4\xac\xaa\xc7\xa7\x8c \xa8\xb5\xc8\xb1\xa9 \xc5\xaa\xc6\xa7\xb3\xc2\xa9.')),
    ('Portuguese', 'Unicode é um padrão que permite aos computadores representar e manipular, de forma consistente, '
        'texto de qualquer sistema de escrita existente.',
        (
            b'Unicode \xe9 um padr\xe3o que permite aos computadores representar e manipular, de forma consistente, '
            b'texto de qualquer sistema de escrita existente.')),
    ('Bengali', 'ইউনিকোড একটি আন্তর্জাতিক বর্ণ সংকেতায়ন ব্যবস্থা।',
        (
            b'\x1f\x13\x87\x89\xa8\xbf\x95\xcb\xa1 \x8f\x95\x9f\xbf \x86\xa8\xcd\xa4\xb0\xcd\x9c\xbe\xa4\xbf\x95 \xac\xb0'
            b'\xcd\xa3 \xb8\x82\x95\xc7\xa4\xbe\xaf\xbc\xa8 \xac\xcd\xaf\xac\xb8\xcd\xa5\xbe\x14\xe4')),
    ('Russian', 'Юнико́д — стандарт кодирования символов, позволяющий представить знаки почти всех письменных языков.',
        (
            b'\x12\xae\xbd\xb8\xba\xbe\x04\x01\xb4 \x05\x14 \xc1\xc2\xb0\xbd\xb4\xb0\xc0\xc2 \xba\xbe\xb4\xb8\xc0\xbe\xb2'
            b'\xb0\xbd\xb8\xcf \xc1\xb8\xbc\xb2\xbe\xbb\xbe\xb2, \xbf\xbe\xb7\xb2\xbe\xbb\xcf\xce\xc9\xb8\xb9 \xbf\xc0'
            b'\xb5\xb4\xc1\xc2\xb0\xb2\xb8\xc2\xcc \xb7\xbd\xb0\xba\xb8 \xbf\xbe\xc7\xc2\xb8 \xb2\xc1\xb5\xc5 \xbf\xb8'
            b'\xc1\xcc\xbc\xb5\xbd\xbd\xcb\xc5 \xcf\xb7\xcb\xba\xbe\xb2.')),
    ('Japanese', 'ユニコードとは、符号化文字集合や文字符号化方式などを定めた、文字コードの業界規格である。',
        (
            b'\x16\xc6\xab\x93\xdc\xa9\x15\xa8\xaf\x08\x01\x0f{&S\xf7S\x16e\x87[W\x96\xc6T\x080\x84e\x87[W{&S\xf7S\x16e'
            b'\xb9_\x0f\xe5\xaa\xa9\xd2\x0e[\x9a\xc1\x9f\x08\x01\x0fe\x87[W\xe5\xf3\x16\xdc\xa9\x15\xae\x0fimuL\x89'
            b'\x8fh<\xe5\xa7\x82\xcb\x08\x02')),
    ('Punjabi', 'ਯੂਨੀਕੋਡ ਹਰ ਇੱਕ ਅੱਖਰ ਲਈ ਇੱਕ ਵਿਸ਼ੇਸ਼ ਗਿਣਤੀ ਪ੍ਰਦਾਨ ਕਰਦਾ ਹੈ, ਚਾਹੇ ਕੋਈ ਵੀ ਕੰਪਿਊਟਰ ਪਲੇਟਫਾਰਮ, ਪ੍ਰੋਗਰਾਮ ਅਤੇ'
        'ਕੋਈ ਵੀ ਭਾਸ਼ਾ ਹੋਵੇ।',
        (
            b'\x1f\x14\xaf\xc2\xa8\xc0\x95\xcb\xa1 \xb9\xb0 \x87\xf1\x95 \x85\xf1\x96\xb0 \xb2\x88 \x87\xf1\x95 \xb5\xbf'
            b'\xb8\xbc\xc7\xb8\xbc \x97\xbf\xa3\xa4\xc0 \xaa\xcd\xb0\xa6\xbe\xa8 \x95\xb0\xa6\xbe \xb9\xc8, \x9a\xbe\xb9'
            b'\xc7 \x95\xcb\x88 \xb5\xc0 \x95\xf0\xaa\xbf\x8a\x9f\xb0 \xaa\xb2\xc7\x9f\xab\xbe\xb0\xae, \xaa\xcd\xb0\xcb'
            b'\x97\xb0\xbe\xae \x85\xa4\xc7\x95\xcb\x88 \xb5\xc0 \xad\xbe\xb8\xbc\xbe \xb9\xcb\xb5\xc7\x14\xe4'))
]


for language, text, scsu_byte_arrrays in example_sentences:
    output_array, counter, char_counter = scsu.decode(scsu_byte_arrrays, None)
    print(language)
    print(text)
    for i in output_array:
        print(hex(i), ' ', sep='', end='')
    print()
    if output_array.decode('utf-8') == text:
        print('Decode success.')
    else:
        print('Decode fail.')
    print(output_array.decode('utf-8'))
    print()

