from __future__ import generator_stop

import collections
import curses
import math

import pyaudio


BITRATE = 44100

REST = None
SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
fixed_note, fixed_octave, fixed_freq = SCALE.index('A'), 4, 880
A = 2 ** (1 / 12)
sqrt3 = 3 ** 0.5


def get_freq(note, octave=4):
    _note_delta = SCALE.index(note) - fixed_note
    half_step_delta = (octave - fixed_octave) * len(SCALE) + _note_delta
    return fixed_freq * (A ** half_step_delta)


class Sequencer:
    """
    Track notes to play.
    """
    def __init__(self):
        _p = pyaudio.PyAudio()
        self._stream = _p.open(
            format=_p.get_format_from_width(1),
            channels=1,
            rate=BITRATE,
            frames_per_buffer=2048,
            output=True,
        )
        self._noteforms = {}
        self._notebytes = {}
        self._generate_noteforms()
        self._song_wavedata = None

        try:
            with open('song.txt', 'r') as file:
                data = eval(file.read())
            if isinstance(data, list):
                data = {k: v for k, v in enumerate(data) if v}
            self._notes = collections.defaultdict(set, data)
            self.compile_song()
        except OSError:
            self._notes = collections.defaultdict(set)

    def _generate_noteforms(self):
        for octave in range(3, 6):
            for note in SCALE:
                nf = self._noteforms[note, octave] = list(get_note_form(get_freq(note, octave)))
                self._notebytes[note, octave] = bytes(map(sin_to_byte, nf))
        NUMBER_OF_FRAMES = int(BITRATE * 1/6)
        self._noteforms[REST] = [0] * NUMBER_OF_FRAMES

    def toggle_note(self, x, note):
        """
        Returns True if the note was added, False if removed.
        """
        note_set = self._notes[x]
        note_set ^= {note}
        if not note_set:
            del self._notes[x]
        self._song_wavedata = None  # clear the song cache.
        return note in note_set

    def song_notes(self):
        notes = sorted(self._notes.items())
        if not notes:
            return
        last, _ = notes[-1]
        notes = iter(notes)
        next_key, next_value = next(notes)
        for key in range(last + 1):
            if key == next_key:
                yield next_value
                try:
                    next_key, next_value = next(notes)
                except StopIteration:
                    return
            else:
                yield [REST]

    def compile_song(self):
        song_freqs = (
            zip(*[
                self._noteforms[note]
                for note in note_group
            ])
            for note_group in self.song_notes()
        )
        self._song_wavedata = [
            sin_to_byte(sum(group))
            for freqs in song_freqs
            for group in freqs
        ]

    def play_song(self):
        if self._song_wavedata is None:
            self.compile_song()
        self._stream.write(bytes(self._song_wavedata))

    def play_note(self, note, octave):
        self._stream.write(self._notebytes[note, octave])


def clamp(low, num, high):
    return sorted([low, num, high])[1]


def interpolate(num_frames, shape):
    s = iter(sorted(shape.items()))
    time1, amp1 = next(s)
    for x in range(num_frames):
        frac = x / num_frames
        while frac >= time1:
            time0, amp0 = time1, amp1
            time1, amp1 = next(s)
        yield (frac - time0) * (amp1 - amp0) / (time1 - time0) + amp0


def get_note_form(freq, length=1/6):
    NUMBER_OF_FRAMES = int(BITRATE * length)
    for x, amp in enumerate(interpolate(NUMBER_OF_FRAMES, {0.0: 0.0, 0.005: 1.0, 0.25: 0.5, 0.9: 0.1, 1.0: 0.0})):
        # "piano": https://dsp.stackexchange.com/a/46606
        x /= (BITRATE / freq)
        yield (0.25 * math.sin(3 * math.pi * x) + 0.25 * math.sin(math.pi * x) + sqrt3 / 2 * math.cos(math.pi * x)) * amp


def sin_to_byte(sin_val):
    return clamp(0, int(sin_val * 100 + 128), 255)


GRAY_ID = 13

class Board:
    """
    Interface between terminal and sequencer model.
    """
    OFFSET_X = 1

    def __init__(self):
        self._octave_min = 3
        self._octave_max = 5
        self._octave_range = self._octave_max + 1 - self._octave_min

        self._sequencer = Sequencer()
        self._scroll = 0

    def _get_note(self, y):
        return SCALE[::-1][y % len(SCALE)]

    def _to_y(self, note, octave):
        return SCALE[::-1].index(note) + (self._octave_max - octave) * len(SCALE)

    def draw(self, screen):
        for y in range(self._octave_range * len(SCALE)):
            # leading line
            screen.addstr(y, 0, ' ' if self._scroll else '│')
            # horizontal lines
            attr = 0 if (y + 1) % len(SCALE) else curses.A_UNDERLINE
            for x in range(16):
                screen.addstr(y, self.OFFSET_X + x * 4, '--', attr)
                screen.addstr(y, self.OFFSET_X + x * 4 + 2, '--', attr | curses.color_pair(GRAY_ID))
        # Scroll display
        if self._scroll:
            for y in range(1, self._octave_range):
                screen.addstr(y * len(SCALE) - 1, 0, '<')
                screen.addstr(y * len(SCALE), 0, '<')
        # Notes!
        for x, column in self._sequencer._notes.items():
            if 0 <= x - self._scroll < 64:
                for note, octave in column:
                    self._draw_note(screen, x - self._scroll + self.OFFSET_X, self._to_y(note, octave))

    def _draw_note(self, screen, x, y, is_note=True):
        if is_note:
            char = self._get_note(y)[-1]
            color = curses.color_pair(-y % len(SCALE) or len(SCALE))
        else:
            char = '-'
            color = curses.color_pair(0 if (x - self.OFFSET_X) % 4 < 2 else GRAY_ID)
        screen.addstr(
            y, x, char, (0 if (y + 1) % len(SCALE) else curses.A_UNDERLINE) | color)

    def handle_click(self, *, mx, my, screen):
        if not (0 <= mx - self.OFFSET_X < 64 and 0 <= my < self._octave_range * len(SCALE)):
            return

        octave = self._octave_max - my // len(SCALE)
        note = self._get_note(my)

        is_note = self._sequencer.toggle_note(mx + self._scroll - self.OFFSET_X, (note, octave))
        if is_note:
            self._sequencer.play_note(note, octave)
        self._draw_note(screen, mx, my, is_note)

    def handle_key(self, event, screen):
        if event == ord(' '):
            self._sequencer.play_song()
        elif event == ord('s'):
            with open('song.txt', 'w') as file:
                file.write(repr(dict(self._sequencer._notes)))
        elif event == ord('a'):
            if self._scroll > 0:
                self._scroll -= 4
                self.draw(screen)
        elif event == ord('d'):
            self._scroll += 4
            self.draw(screen)


def main():
    print("please wait...")
    board = Board()
    try:
        screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.curs_set(0)
        screen.keypad(1)
        curses.mousemask(1)

        curses.init_pair(1, 161, 0)  # C
        curses.init_pair(2, 203, 0)
        curses.init_pair(3, 209, 0)
        curses.init_pair(4, 214, 0)
        curses.init_pair(5, 185, 0)
        curses.init_pair(6, 106, 0)
        curses.init_pair(7, 71, 0)
        curses.init_pair(8, 72, 0)
        curses.init_pair(9, 67, 0)
        curses.init_pair(10, 62, 0)
        curses.init_pair(11, 97, 0)
        curses.init_pair(12, 132, 0)
        curses.init_pair(GRAY_ID, 8, 0)
        board.draw(screen)

        while True:
            event = screen.getch()
            if event == ord("q"): break
            elif event == curses.KEY_MOUSE:
                _, mx, my, _, btype = curses.getmouse()
                if btype == curses.BUTTON1_RELEASED:
                    board.handle_click(mx=mx, my=my, screen=screen)
            else:
                board.handle_key(event, screen)
    finally:
        curses.endwin()

if __name__ == '__main__':
    main()
