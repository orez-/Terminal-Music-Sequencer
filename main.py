import collections
import curses
import math

import pyaudio


BITRATE = 44100

SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
fixed_note, fixed_octave, fixed_freq = SCALE.index('A'), 4, 880
A = 2 ** (1 / 12)


def get_freq(note, octave=4):
    _note_delta = SCALE.index(note) - fixed_note
    half_step_delta = (octave - fixed_octave) * len(SCALE) + _note_delta
    return fixed_freq * (A ** half_step_delta)


def iter_rstrip(iterable, predicate):
    buffer = collections.deque()
    for elem in iterable:
        if predicate(elem):
            yield from buffer
            yield elem
            buffer.clear()
        else:
            buffer.append(elem)


class Sequencer:
    """
    Track notes to play.
    """
    def __init__(self):
        try:
            with open('song.txt', 'r') as file:
                self._notes = eval(file.read())
        except OSError:
            self._notes = [set() for _ in range(64)]

    def toggle_note(self, x, note):
        """
        Returns True if the note was added, False if removed.
        """
        note_set = self._notes[x]
        note_set ^= {note}
        return note in note_set

    def play_song(self):
        _p = pyaudio.PyAudio()
        stream = _p.open(
            format=_p.get_format_from_width(1),
            channels=1,
            rate=BITRATE,
            frames_per_buffer=2048,
            output=True,
        )
        length = 1 / 6
        song_freqs = iter_rstrip((
            [
                get_freq(note, octave)
                for note, octave in notes
            ]
            for notes in self._notes
        ), bool)
        wavedata = (
            note
            for freqs in song_freqs
            for note in get_note_form(freqs, length)
        )
        stream.write(bytes(wavedata))
        stream.stop_stream()
        stream.close()
        _p.terminate()


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


def get_note_form(freqs, length=1/6):
    NUMBER_OF_FRAMES = int(BITRATE * length)
    if not freqs:
        for _ in range(NUMBER_OF_FRAMES):
            yield 128
        return
    for x, amp in enumerate(interpolate(NUMBER_OF_FRAMES, {0.0: 0.0, 0.005: 1.0, 0.25: 0.5, 0.9: 0.1, 1.0: 0.0})):
        num = sum(
            math.sin(x / ((BITRATE / freq) / math.pi))
            for freq in freqs
        ) * amp

        yield clamp(0, int(num * 100 + 128), 255)


GRAY_ID = 13

class Board:
    """
    Interface between terminal and sequencer model.
    """
    def __init__(self):
        self._sequencer = Sequencer()

    def _get_note(self, y):
        return SCALE[::-1][y % len(SCALE)]

    def _to_y(self, note, octave):
        return SCALE[::-1].index(note) + (5 - octave) * len(SCALE)

    def draw(self, screen):
        for y in range(3 * len(SCALE)):
            attr = 0 if (y + 1) % len(SCALE) else curses.A_UNDERLINE
            for x in range(16):
                screen.addstr(y, x * 4, '--', attr)
                screen.addstr(y, x * 4 + 2, '--', attr | curses.color_pair(GRAY_ID))
        for x, column in enumerate(self._sequencer._notes):
            for note, octave in column:
                self._draw_note(screen, x, self._to_y(note, octave))

    def _draw_note(self, screen, x, y, is_note=True):
        if is_note:
            char = self._get_note(y)[-1]
            color = curses.color_pair(-y % len(SCALE) or len(SCALE))
        else:
            char = '-'
            color = curses.color_pair(0 if x % 4 < 2 else GRAY_ID)
        screen.addstr(
            y, x, char, (0 if (y + 1) % len(SCALE) else curses.A_UNDERLINE) | color)

    def handle_click(self, *, mx, my, screen):
        if not (0 <= mx < 64 and 0 <= my < 3 * len(SCALE)):
            return

        octave = 5 - my // len(SCALE)
        note = self._get_note(my)

        is_note = self._sequencer.toggle_note(mx, (note, octave))
        self._draw_note(screen, mx, my, is_note)

    def handle_key(self, event):
        if event == ord(' '):
            self._sequencer.play_song()
        elif event == ord('s'):
            with open('song.txt', 'w') as file:
                file.write(repr(self._sequencer._notes))


def main():
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
                board.handle_key(event)
    finally:
        curses.endwin()

if __name__ == '__main__':
    main()
