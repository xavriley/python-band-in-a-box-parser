# This code is a direct port of the BIAB parser from the MuseScore project

from fractions import Fraction
import mido
import numpy as np

# Should be called time signatures
STYLES = [
    (4, 4),  # Jazz Swing
    (12, 8), # Country 12/8
    (4, 4),  # Country 4/4
    (4, 4),  # Bossa Nova
    (4, 4),  # Ethnic
    (4, 4),  # Blues Shuffle
    (4, 4),  # Blues Straight
    (3, 4),  # Waltz
    (4, 4),  # Pop Ballad
    (4, 4),  # should be Rock Shuffle
    (4, 4),  # lite Rock
    (4, 4),  # medium Rock
    (4, 4),  # Heavy Rock
    (4, 4),  # Miami Rock
    (4, 4),  # Milly Pop
    (4, 4),  # Funk
    (3, 4),  # Jazz Waltz
    (4, 4),  # Rhumba
    (4, 4),  # Cha Cha
    (4, 4),  # Bouncy
    (4, 4),  # Irish
    (12, 8), # Pop Ballad 12/8
    (12, 8), # Country12/8 old
    (4, 4),  # Reggae
]

MAX_BARS = 255
_events = []
_barType = np.zeros(MAX_BARS)
bbDivision = 120

def timesigZ(idx):
    return STYLES[idx][0]

def timesigN(idx):
    return STYLES[idx][1]

class BBChord():
    def __init__(self):
        self.beat = 0
        self.bass = ''
        self.root = ''
        self.extension = ''

def getint(b):
    return int.from_bytes(b, byteorder='little')

def parse_biab(path):
    xs = np.fromfile(path, dtype='<c')

    idx = 0

    version = xs[idx]
    idx += 1

    title_length = getint(xs[idx])
    idx += 1

    title = ''.join(np.char.decode(xs[idx:(idx+title_length)]))
    idx += title_length

    # skip two, read third
    idx += 1
    idx += 1

    style = getint(xs[idx]) - 1
    idx += 1
    key_idx = getint(xs[idx])

    # map D# G# A#   to Eb Ab Db
    # major   C, Db,  D, Eb,  E,  F, Gb,  G, Ab,  A, Bb,  B, C#, D#, F#, G#, A#
    # minor   C, Db,  D, Eb,  E,  F, Gb,  G, Ab,  A, Bb,  B, C#, D#, F#, G#, A#
    key_lookup = [
        0,       0,  -5,  2, -3,  4, -1, -6,  1, -4,  3, -2,  5,  7, -3,  6, -4, -2,
        -3,      4,  -1, -6,  1, -4,  3, -2,  5,  0, -5,  2,  4,  6,  3,  5, 7
    ]
    key = key_lookup[key_idx]

    idx += 1
    bpm_main = getint(xs[idx])
    idx += 1
    bpm_frac = getint(xs[idx]) << 8
    bpm = bpm_main + bpm_frac

    idx += 2

    # Read bar types
    bar = getint(xs[idx]) # starting bar number
    while bar < 255:
        idx += 1
        val = getint(xs[idx])
        if val == 0:
            idx += 1
            bar += getint(xs[idx])
        else:
            bar +=1
            _barType[bar] = val
            print(f"bar type bar: {bar} val: {val}")

    # Read chord extensions
    chords = []
    beat: int = 0
    while beat < (MAX_BARS * 4):
        idx += 1
        val = getint(xs[idx])
        if val == 0:
            idx += 1
            beat += getint(xs[idx])
        else:
            # we found a chord
            c = BBChord()
            c.extension = val
            c.beat = int(beat * (timesigZ(style) / timesigN(style)))
            beat += 1
            chords.append(c)

    # Read chord roots
    roots = 0
    maxbeat = 0
    beat: int = 0
    while beat < (MAX_BARS * 4):
        idx += 1
        val = getint(xs[idx])
        if val == 0:
            idx += 1
            beat += getint(xs[idx])
        else:
            root = int(val % 18)
            bass = int(root - 1 + val / 18) % 18 + 1
            if root == bass:
                bass = 0

            ibeat = beat * (timesigZ(style) / timesigN(style))
            if ibeat != chords[roots].beat:
                print("Inconsistent chord type and chord beat")

            chords[roots].root = root
            chords[roots].bass = bass

            if maxbeat < beat:
                maxbeat = beat

            roots += 1
            beat += 1

    measures = ((maxbeat + timesigZ(style) - 1) / timesigZ(style)) + 1;

    if roots != len(chords):
        print(f"Chord parsing error: Root count ({roots}) != Extension count ({len(chords)})")

    print(f"Measure count {measures}")

    # from the original - // ??
    if getint(xs[idx]) == 1:
        print(f"Skipping {getint(xs[idx])} at {idx}")
        idx += 1

    startChorus = getint(xs[idx])
    idx += 1
    endChorus = getint(xs[idx])
    idx += 1
    repeats = getint(xs[idx])
    idx += 1

    if startChorus >= endChorus:
        startChorus = 0
        endChorus = 0
        repeats = -1

    # read style file
    found = False
    for i in range(len(xs)):
        if xs[i] == b'\x42':
            if getint(xs[i + 1]) < 16:
                for k in range(i + 2, i + 18):
                    try:
                        maybe_string = ''.join(np.char.decode(xs[k:k+4]))
                    except UnicodeDecodeError:
                        maybe_string = ''
                    if maybe_string == '.STY':
                        found = True
                        print("found a style file")
                        break
            if found:
                idx = i + 1
                break

    if not found:
        print("ERROR: Style file not found")
        exit(1)

    styleNameLen = getint(xs[idx]) + 1
    idx += 1
    styleName = ''.join(np.char.decode(xs[idx:idx+styleNameLen]))

    # midi events
    eventStart = getint(xs[-4]) + getint(xs[-3]) * 256
    eventCount = getint(xs[-2]) + getint(xs[-1]) * 256

    # MuseScore has a different concept of ticks
    # https://github.com/musescore/MuseScore/pull/4630
    endTick = Fraction(int(measures * bbDivision * 4 * timesigZ(style)),
                       timesigN(style))

    notes = []

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    if eventCount == 0:
        print("No events found")
    else:
        idx = eventStart
        lastDelta = 0
        print(f"Events found at {eventStart}")
        for i in range(eventCount):
            msg = mido.parse(xs[idx+4:idx+8])
            type = getint(xs[idx + 4]) & 0xf0
            if type == 0x90:
                # 0x90 is note on
                channel = getint(xs[idx + 7])
                tick = (getint(xs[idx])
                        + (getint(xs[idx + 1]) << 8)
                        + (getint(xs[idx + 2]) << 16)
                        + (getint(xs[idx + 3]) << 24))
                # tick -= 4 * bbDivision
                msg = mido.Message(type='note_on',
                                   channel=channel,
                                   note=getint(xs[idx + 5]),
                                   velocity=getint(xs[idx + 6]))

                deltaTime = (getint(xs[idx + 8])
                        + (getint(xs[idx + 9]) << 8)
                        + (getint(xs[idx + 10]) << 16)
                        + (getint(xs[idx + 11]) << 24))

                if deltaTime == 0:
                    if lastDelta == 0:
                        print(f"note event of length 0 at {idx}")
                        continue
                    deltaTime = lastDelta

                lastDelta = deltaTime

                noteOff = mido.Message(type='note_off',
                                       channel=channel,
                                       note=getint(xs[idx + 5]),
                                       velocity=getint(xs[idx + 6]),
                                       time=int(mido.tick2second(tick + deltaTime, 120, mido.bpm2tempo(bpm))))
                track.append(msg)
                track.append(noteOff)

            elif type == 0xb0 or type == 0xc0:
                # ignore control
                pass
            elif type == 0:
                break
            else:
                print(f"Unknown event type {str(xs[idx + 4])}")
                break

            idx += 12


    mid.save('road_song.mid')

    print(title)
    print(style)
    print(key)
    print(bpm)
    print(startChorus)
    print(endChorus)
    print(repeats)
    # print('\n'.join([f"{c.beat} {c.bass} {c.root} {c.extension}" for c in chords]))
    print(styleName)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    parse_biab('/Users/xavriley/Downloads/Wes-in-a-Box-HWR-Free-songs/Wes in a Box (HWR) Free songs/Road Song (1968).MGU')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
