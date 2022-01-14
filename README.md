# Band-in-a-Box Parser

## please note: this is a work in progress

This is an attempt to extract MIDI information from a Band-in-a-Box file (`.mgu` file extension).

The code is more or less a port from the existing code in the MuseScore codebase [here](https://github.com/musescore/MuseScore/blob/b587e98b48b5bc0e08522f77070b6ba51ec966eb/src/importexport/bb/internal/bb.cpp)

It manages to extract the events successfully although the alignment is not 100% correct yet.