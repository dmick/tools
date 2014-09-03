#!/usr/bin/env python

from Tkinter import *
import os

allfiles = list()
selected = list()
output = list()

FONT=('Arial', '12')
NUMFILT=3
TITLE="FileFilter"

filts = list()
filtstrings = list()

def exit_app(event):
    print '\n'.join(output)
    sys.exit()


def relist():
    global selected

    filtexprs = [w.get() or '' for w in filts]
    print "relist: ", filtexprs

    # reduce allfiles to a list of entries containing all the filtexprs
    selected = [item for item in allfiles if \
                  all((filt in item) for filt in filtexprs)]

    # sort em and refill the listbox
    selected.sort()
    filtout.delete(0, END)
    maxlen = -1
    for filename in selected:
        filtout.insert(END, filename)
    filtout.config(height=20, width=len(max(selected, key=len)))


def add_selected_to_output(event):
    add_to_output(selected, clear=True)


def add_to_output(name, clear=False):
    if not isinstance(name, list):
        name = [name]
    for n in name:
        output.append(n)
        outputlb.insert(END, n)
    if clear:
        for filt in filts:
            filt.delete(0, END)
        filts[0].focus()
    relist()




filtout = outputlb = None

def main():
    global filtout, outputlb, allfiles
    root = Tk()
    root.title(TITLE)

    for i in xrange(0, NUMFILT):
        filtstrings.append(StringVar())
        filtstrings[-1].trace("w", lambda x,y,z: relist())
        w = Entry(font=FONT, textvariable=filtstrings[-1])
        filts.append(w)
        w.grid(row=0, column=i, sticky=W+E)
        root.columnconfigure(i, weight=1)

    # don't take focus, so tab moves around filt widgets but not listboxes
    filtout = Listbox(font=FONT, takefocus=0)
    filtout.grid(row=1, columnspan=NUMFILT, sticky=W+E+N+S)
    outputlb = Listbox(font=FONT, takefocus=0, selectmode=EXTENDED)
    outputlb.grid(row=2, columnspan=NUMFILT, sticky=W+E+N+S)

    # let the second and third rows (with listboxes) eat up any resizing
    root.rowconfigure(1, weight=1)
    root.rowconfigure(2, weight=1)

    for i, w in enumerate(filts):
        w.bind("<Return>", add_selected_to_output)

    # doubleclick in the filtout listbox adds to the output
    filtout.bind("<Double-Button-1>", lambda x: add_to_output(filtout.get(filtout.curselection()[0])))

    # Del with a selection in the output listbox removes the selection

    for dirpath, dirs, files in os.walk('.'):
        allfiles.extend([os.path.join(dirpath, f) for f in files])

    # show the initial list
    relist()

    # set the initial focus
    filts[0].focus()

    # allow ^C anywhere in the app to exit
    root.bind("<Control-c>", exit_app)

    # loop until terminated, then print output list
    root.mainloop()
    exit_app(None)

if __name__ == "__main__":
    main()

