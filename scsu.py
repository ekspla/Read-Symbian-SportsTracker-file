#coding:utf-8
"""This is a ported version of Roman Czyborra's decoder written in C.
"""
#/* http://czyborra.com/scsu/scsu.c
# * 1998-08-04 written by Roman Czyborra@dds.nl
# * on Andrea's balcony in North Amsterdam on 1998-08-04
# * 
# * 1998-10-01 Richard Verhoeven <rcb5@win.tue.nl>
# * corrected my haphazard "if" after UQU to "else if".
# * 
# * 2014-09-29 Likasoft <support@likasoft.com>
# * pointed out all the copied 0x3800 got the 0x3380 wrong!
# *
# * This is a deflator to UTF-8 output for input compressed in SCSU,
# * the (Reuters) Standard Compression Scheme for Unicode as described
# * in http://www.unicode.org/unicode/reports/tr6.html
# *
# * Simply compile it with make scsu or cc -o scsu scsu.c and add
# *
# * text/plain; scsu < %s | xviewer yudit; \
# *   test=case %{charset} in [Ss][Cc][Ss][Uu])\;\; *)[ ]\; esac
# *
# * to your mailcap.
# *
# * This is freeware as long as you properly attribute my contribution.  */

# /* SCSU uses the following variables and default values: */

start = [0x0000,0x0080,0x0100,0x0300,0x2000,0x2080,0x2100,0x3000]
slide = [0x0080,0x00C0,0x0400,0x0600,0x0900,0x3040,0x30A0,0xFF00]
win = [
    0x0000, 0x0080, 0x0100, 0x0180, 0x0200, 0x0280, 0x0300, 0x0380,
    0x0400, 0x0480, 0x0500, 0x0580, 0x0600, 0x0680, 0x0700, 0x0780,
    0x0800, 0x0880, 0x0900, 0x0980, 0x0A00, 0x0A80, 0x0B00, 0x0B80,
    0x0C00, 0x0C80, 0x0D00, 0x0D80, 0x0E00, 0x0E80, 0x0F00, 0x0F80,
    0x1000, 0x1080, 0x1100, 0x1180, 0x1200, 0x1280, 0x1300, 0x1380,
    0x1400, 0x1480, 0x1500, 0x1580, 0x1600, 0x1680, 0x1700, 0x1780,
    0x1800, 0x1880, 0x1900, 0x1980, 0x1A00, 0x1A80, 0x1B00, 0x1B80,
    0x1C00, 0x1C80, 0x1D00, 0x1D80, 0x1E00, 0x1E80, 0x1F00, 0x1F80,
    0x2000, 0x2080, 0x2100, 0x2180, 0x2200, 0x2280, 0x2300, 0x2380,
    0x2400, 0x2480, 0x2500, 0x2580, 0x2600, 0x2680, 0x2700, 0x2780,
    0x2800, 0x2880, 0x2900, 0x2980, 0x2A00, 0x2A80, 0x2B00, 0x2B80,
    0x2C00, 0x2C80, 0x2D00, 0x2D80, 0x2E00, 0x2E80, 0x2F00, 0x2F80,
    0x3000, 0x3080, 0x3100, 0x3180, 0x3200, 0x3280, 0x3300, 0x3380,
    0xE000, 0xE080, 0xE100, 0xE180, 0xE200, 0xE280, 0xE300, 0xE380,
    0xE400, 0xE480, 0xE500, 0xE580, 0xE600, 0xE680, 0xE700, 0xE780,
    0xE800, 0xE880, 0xE900, 0xE980, 0xEA00, 0xEA80, 0xEB00, 0xEB80,
    0xEC00, 0xEC80, 0xED00, 0xED80, 0xEE00, 0xEE80, 0xEF00, 0xEF80,
    0xF000, 0xF080, 0xF100, 0xF180, 0xF200, 0xF280, 0xF300, 0xF380,
    0xF400, 0xF480, 0xF500, 0xF580, 0xF600, 0xF680, 0xF700, 0xF780,
    0xF800, 0xF880, 0xF900, 0xF980, 0xFA00, 0xFA80, 0xFB00, 0xFB80,
    0xFC00, 0xFC80, 0xFD00, 0xFD80, 0xFE00, 0xFE80, 0xFF00, 0xFF80,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x00C0, 0x0250, 0x0370, 0x0530, 0x3040, 0x30A0, 0xFF60]

# /* deflation algorithm */

def decode(byte_array, size=None):
    """Decode SCSU encoded bytes/bytearray to UTF-8.

    Args:
        byte_array: SCSU encoded bytes or bytearray.  The length can be longer 
            than necessary.
        size: number of the characters to be decoded, defaults to the full 
            length of the byte_array.

    Returns:
        output_array: decoded bytearray in UTF-8.
        counter: number of bytes read from the input byte_array.
        char_counter: number of decoded characters.
    """
    input_array = bytearray(byte_array)
    if size is None:
        size = len(input_array) # Maximum length of characters to be decoded.
    char_counter = 0 # Number of decoded characters.
    output_array = bytearray()
    counter = 0
    active = 0

    def nextchar(input_array):
        # /* read one byte if available */
        nonlocal counter
        if input_array:
            c = input_array.pop(0)
            counter += 1
            return c
        else:
            raise LookupError

    def output(c, output_array):
        char_count = 0
        nonlocal d

        # /* join UTF-16 surrogates without any pairing sanity checks */

        if 0xD800 <= c <= 0xDBFF:
            d = c & 0x3FF
            return char_count

        if 0xDC00 <= c <= 0xDFFF:
            c = c + 0x2400 + d * 0x400

        # /* output one character as UTF-8 multibyte sequence */
        if c < 0x80:
            output_array.append(c)
            char_count += 1

        elif c < 0x800:
            output_array.append(0xC0 | c>>6)
            output_array.append(0x80 | c & 0x3F)
            char_count += 1

        elif c < 0x10000:
            output_array.append(0xE0 | c>>12)
            output_array.append(0x80 | c>>6 & 0x3F)
            output_array.append(0x80 | c & 0x3F)
            char_count += 1

        elif c < 0x200000:
            output_array.append(0xF0 | c>>18)
            output_array.append(0x80 | c>>12 & 0x3F)
            output_array.append(0x80 | c>>6 & 0x3F)
            output_array.append(0x80 | c & 0x3F)
            char_count += 1

        return char_count


    while char_counter < size:
        try:
            c = nextchar(input_array)

            if c >= 0x80:
                char_counter += output(c - 0x80 + slide[active], output_array)

            elif 0x20 <= c <= 0x7F:
                char_counter += output(c, output_array)

            elif c in {0x0, 0x9, 0xA, 0xC, 0xD}:
                char_counter += output(c, output_array)

            elif 0x1 <= c <= 0x8: # /* SQn */
                # /* single quote */
                d = nextchar(input_array)
                if d < 0x80:
                    char_counter += output(d + start[c - 0x1], output_array)
                else:
                    char_counter += output(d - 0x80 + slide[c - 0x1], 
                                           output_array)

            elif 0x10 <= c <= 0x17: # /* SCn */
                # /* change window */
                active = c - 0x10

            elif 0x18 <= c <= 0x1F: # /* SDn */
                # /* define window */
                active = c - 0x18
                slide[active] = win[nextchar(input_array)]

            elif c == 0xB: # /* SDX */
                c = nextchar(input_array)
                d = nextchar(input_array)
                active = c >> 5
                slide[active] = 0x10000 + (((c & 0x1F) << 8 | d) << 7)

            elif c == 0xE: # /* SQU */
                c = nextchar(input_array)
                char_counter += output(c << 8 | nextchar(input_array), 
                                       output_array)

            elif c == 0xF: # /* SCU */
                # /* change to Unicode mode */
                mode = 1

                while mode and char_counter < size:
                    c = nextchar(input_array)

                    if c <= 0xDF or c >= 0xF3:
                        char_counter += output(c << 8 | nextchar(input_array), 
                                               output_array)

                    elif c == 0xF0: # /* UQU */
                        c = nextchar(input_array)
                        char_counter += output(c << 8 | nextchar(input_array), 
                                               output_array)

                    elif 0xE0 <= c <= 0xE7: # /* UCn */
                        active = c - 0xE0
                        mode = 0

                    elif 0xE8 <= c <= 0xEF: # /* UDn */
                        active = c - 0xE8
                        slide[active] = win[nextchar(input_array)]
                        mode = 0

                    elif c == 0xF1: # /* UDX */
                        c = nextchar(input_array)
                        d = nextchar(input_array)
                        active = c >> 5
                        slide[active] = 0x10000 + (((c & 0x1F) << 8 | d) << 7)
                        mode = 0

        except LookupError:
            break

    return output_array, counter, char_counter
