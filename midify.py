import argparse
import os.path
from pathlib import Path
import re


class Pitch:
    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return f"{self.value}"

    def fromNum(num: int) -> 'Pitch':
        if -5 < num < 22:
            return Pitch(chr(ord('e') + num))
        elif num < -4:
            return Pitch(chr(ord('N') + (num + 5)))
        raise RuntimeError(f"Cannot convert number {num} to pitch")

    def fromLetter(letter: str) -> 'Pitch':
        return Pitch(letter)


class Accidentals:
    def __init__(self, sharps: list[Pitch], flats: list[Pitch], explicitNaturals: list[Pitch] = []):
        self.sharps = sharps
        self.flats = flats
        self.explicitNaturals = explicitNaturals

    def fromGlobalAndLocal(globalAccidentals: 'Accidentals', localAccidentals: 'Accidentals') -> 'Accidentals':
        return Accidentals(sharps=globalAccidentals.sharps + localAccidentals.sharps,
                           flats=globalAccidentals.flats + localAccidentals.flats,
                           explicitNaturals=localAccidentals.explicitNaturals)


class Note:
    def __init__(self, pitch: Pitch, start: int, duration: int, accidentals: Accidentals):
        self.pitch = pitch
        self.start = start
        self.duration = duration
        self.accidentals = accidentals

    def __repr__(self):
        return f"N({self.toMidiPitch()}@{self.start}+{self.duration})"

    def toMidiPitch(self) -> int:
        conv = {'A': 21, 'B': 23, 'C': 24, 'D': 26,
                'E': 28, 'F': 29, 'G': 31, 'H': 33, 'I': 35, 'J': 36, 'K': 38,
                'L': 40, 'M': 41, 'N': 43, 'a': 45, 'b': 47, 'c': 48, 'd': 50,
                'e': 52, 'f': 53, 'g': 55, 'h': 57, 'i': 59, 'j': 60, 'k': 62,
                'l': 64, 'm': 65, 'n': 67, 'o': 69, 'p': 71, 'q': 72, 'r': 74,
                's': 76, 't': 77, 'u': 79, 'v': 81, 'w': 83, 'x': 84, 'y': 86,
                'z': 88}
        base = conv[self.pitch.value]
        if self.pitch in self.accidentals.explicitNaturals:
            pass
        elif self.pitch in self.accidentals.sharps:
            base += 1
        elif self.pitch in self.accidentals.flats:
            base -= 1
        return base

    def startMidiBytes(self, prevNote: 'Note' = None) -> bytes:
        if prevNote is not None:
            delta = self.start - (prevNote.start + prevNote.duration)
            if delta < 128:
                return bytes([delta])
            suffix = bytearray()
            suffix.insert(0, delta % 128)
            value = delta // 128
            while value > 0:
                suffix.insert(0, (value % 128) + 128)
                value = value // 128
            return suffix
        return bytes([0])

    def endMidiBytes(self) -> bytes:
        if (self.duration) < 128:
            return (self.duration).to_bytes(1, 'big')
        suffix = bytearray()
        suffix.insert(0, (self.duration) % 128)
        value = (self.duration) // 128
        while value > 0:
            suffix.insert(0, (value % 128) + 128)
            value = value // 128
        return suffix

    def toMidiBytes(self, prevNote: 'Note' = None) -> bytes:
        pitch = self.toMidiPitch()
        return (self.startMidiBytes(prevNote=prevNote) + 0x90.to_bytes(1, 'big') +
                pitch.to_bytes(1, 'big') + (64).to_bytes(1, 'big') +
                self.endMidiBytes() + 0x80.to_bytes(1, 'big') +
                pitch.to_bytes(1, 'big') + (64).to_bytes(1, 'big'))


def load_files(path: Path) -> dict[str, str]:
    result = {}
    path = Path(path)

    if path.is_file():
        with open(path, 'r', encoding='utf-8') as f:
            result[path.name] = f.read()
    elif path.is_dir():
        for file_path in path.glob('*'):
            if file_path.is_file():
                with open(file_path, 'r', encoding='utf-8') as f:
                    result[file_path.name] = f.read()

    return result


__numbermatcher = re.compile(r"^-?\d+$")


def isNumber(s: str) -> bool:
    return __numbermatcher.fullmatch(s) is not None


def parseArgs(s: str) -> list[str]:
    args = []
    current = ''
    inBraces = 0
    for c in s:
        if c == '{':
            inBraces += 1
            continue
        elif c == '}':
            inBraces -= 1
            if inBraces == 0:
                args.append(current)
                current = ''
            continue
        if inBraces > 0:
            current += c
            continue
        args.append(c)

    return args


def auto_pitch(s: str) -> Pitch:
    if isNumber(s):
        return Pitch.fromNum(int(s))
    else:
        return Pitch.fromLetter(s)


SHARPS = [Pitch.fromNum(x) for x in [8, 5, 9, 6, 3, 7, 4]]
FLATS = [Pitch.fromNum(x) for x in [4, 7, 3, 6, 2, 5, 1]]


def main():
    parser = argparse.ArgumentParser(description='Jindrův absolutně příšerný kód pro parsování MusixTex do MIDI. '
                                                 'Pokud ho nakrmíte daty v trochu jiném formátu než očekává, pravděpodobně se rozbije. '
                                                 'Use on your own danger.',
                                     usage="Zavolejte s povinným pozičním argumentem - cestou k souboru nebo adresáři s .tex soubory.")
    parser.add_argument('path', help='Path to file or directory')
    args = parser.parse_args()

    file_map: dict[str, str] = load_files(args.path)
    print(f"Loaded {len(file_map)} files:")

    for filename, content in file_map.items():
        print(f"- {filename}: {len(content)} characters")
        if not "\\midifyable" in content:
            print("  Not midifyable, skipping.")
            continue
        content = re.sub("(%.*)?\n *", "", content)
        content = content[content.find("\\begin{music}") + len("\\begin{music}"):]
        content = content[:content.find("\\endpiece")]
        content = content.replace(' ', '')
        if "\\generalmeter{\\allabreve}" in content:
            content = content.replace("\\generalmeter{\\allabreve}", "\\generalmeter{\\meterfrac44}")
        metertop = int(re.search(r"\\generalmeter\{\\meterfrac(\d)(\d)}", content).group(1))
        meterbottom = int(re.search(r"\\generalmeter\{\\meterfrac(\d)(\d)}", content).group(2))
        search = re.search(r"\\generalsignature\{?(-?\d)", content)
        if search is None:
            signature = 0
        else:
            signature = int(search.group(1))
        if signature > 0:
            globalAccidentals = Accidentals(sharps=SHARPS[:signature], flats=[])
        elif signature < 0:
            globalAccidentals = Accidentals(sharps=[], flats=FLATS[:abs(signature)])
        else:
            globalAccidentals = Accidentals(sharps=[], flats=[])
        content = content[content.find("\\startpiece") + len("\\startpiece"):]
        content = content.split('\\')
        deltatime = 0
        notes: list[Note] = []
        localAccidentals = Accidentals(sharps=[], flats=[], explicitNaturals=[])
        explicitBeamNoteTicks = 0
        for element in content:
            if element.lower() in ['', "notes", "notesp", 'nnotes', 'nnnotes', 'en', 'xbar', 'alaligne']:
                localAccidentals = Accidentals(sharps=[], flats=[], explicitNaturals=[])
                continue
            commandName = re.search(r"([a-zA-Z]+)", element).group(1)
            argsPart = parseArgs(element[len(commandName):])
            if commandName in ['cl', 'cu', 'ca']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 32
                continue
            elif commandName in ['clp', 'cup', 'cap']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 48, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 48
                continue
            elif commandName in ['ql', 'qu', 'qa']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 64, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 64
                continue
            elif commandName in ['qlp', 'qup', 'qap']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 96, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 96
                continue
            elif commandName in ['hl', 'hu', 'ha']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 128, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 128
                continue
            elif commandName in ['hlp', 'hup', 'hap']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 192, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 192
                continue
            elif commandName in ['wh']:
                notes.append(Note(auto_pitch(argsPart[0]), deltatime, 256, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 256
                continue
            elif commandName == 'sh':
                localAccidentals.sharps.append(auto_pitch(argsPart[0]))
                continue
            elif commandName == 'fl':
                localAccidentals.flats.append(auto_pitch(argsPart[0]))
                continue
            elif commandName == 'na':
                localAccidentals.explicitNaturals.append(auto_pitch(argsPart[0]))
                continue
            elif commandName in ['Dqbl', 'Dqbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 2 * 32
                continue
            elif commandName in ['Tqbl', 'Tqbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[2]), deltatime + 2 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 3 * 32
                continue
            elif commandName in ['Qqbl', 'Qqbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[2]), deltatime + 2 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[3]), deltatime + 3 * 32, 32, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 4 * 32
                continue
            elif commandName in ['Dqbbl', 'Dqbbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 2 * 16
                continue
            elif commandName in ['Tqbbl', 'Tqbbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[2]), deltatime + 2 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 3 * 16
                continue
            elif commandName in ['Qqbbl', 'Qqbbu']:
                if len(argsPart) == 1:
                    argsPart = parseArgs(argsPart[0])
                notes.append(Note(auto_pitch(argsPart[0]), deltatime + 0 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[1]), deltatime + 1 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[2]), deltatime + 2 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                notes.append(Note(auto_pitch(argsPart[3]), deltatime + 3 * 16, 16, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += 4 * 16
                continue
            elif commandName in ['ibu', 'ibl', "Ibu", 'Ibl', 'tbu', 'tbl']:
                explicitBeamNoteTicks = 32
            elif commandName in ['ibbu', 'ibbl', "Ibbu", 'Ibbl', 'nbbu', 'nbbl', 'tbbu', 'tbbl']:
                explicitBeamNoteTicks = 16
            elif commandName in ['qb']:
                notes.append(Note(auto_pitch(argsPart[1]), deltatime, explicitBeamNoteTicks, Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += explicitBeamNoteTicks
            elif commandName in ['qbp']:
                notes.append(Note(auto_pitch(argsPart[1]), deltatime, explicitBeamNoteTicks + (explicitBeamNoteTicks//2), Accidentals.fromGlobalAndLocal(globalAccidentals, localAccidentals)))
                deltatime += explicitBeamNoteTicks + (explicitBeamNoteTicks//2)
            elif "repeat" in commandName:
                deltatime += 1024
                continue
            elif commandName in ['slur', 'tslur', 'isluru', 'islurd']:
                continue #TODO something?
            elif commandName in ['sk', 'hsk']:
                continue
            else:
                print(f"  Unknown element: {element}")
        path = Path(os.path.dirname(args.path))
        path = path.joinpath("midiOutput")
        path.mkdir(exist_ok=True)
        path = path.joinpath(filename + ".mid")
        notesBytes = []
        prevNote = None
        for n in notes:
            notesBytes.append(n.toMidiBytes(prevNote))
            prevNote = n
        bodyBytes = bytearray()
        for b in notesBytes:
            bodyBytes += b
        with path.open("wb") as f:
            f.write(b'MThd\x00\x00\x00\x06\x00\x01\x00\x01\x00\x40MTrk' + (len(bodyBytes)).to_bytes(4, 'big'))
            f.write(bodyBytes)
        print("".join(str(n) for n in notes))


if __name__ == '__main__':
    main()
