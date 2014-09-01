#!/usr/bin/env python

from Tkinter import *
import os
import pprint
pp=pprint.PrettyPrinter().pprint

allfiles = list()
selectlist = list()

FONT=('Arial', '12')

root = Tk()

t1=Entry(font=FONT)
t2=Entry(font=FONT)
t3=Entry(font=FONT)
t1.grid(row=0, sticky=W+E)
t2.grid(row=0, column=1, sticky=W+E)
t3.grid(row=0, column=2, sticky=W+E)
lb=Listbox(font=FONT)
lb.grid(row=1, columnspan=3, sticky=W+E+N+S)

root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=1)
root.columnconfigure(2, weight=1)


def relist(filt1, filt2, filt3):
    global selectlist
    f1 = filt1 or ''
    f2 = filt2 or ''
    f3 = filt3 or ''
    selectlist = [item for item in selectlist if f1 in item and f2 in item and f3 in item]
    selectlist.sort()
    lb.delete(0, END)	
    for f in selectlist:
        lb.insert(END, f)
    lb.config(height=min(40, len(allfiles) / 2))


def t1_callback(event):
    relist(t1.get(), t2.get(), t3.get())
    t2.focus()


def t2_callback(event):
    relist(t1.get(), t2.get(), t3.get())
    t3.focus()


def t3_callback(event):
    relist(t1.get(), t2.get(), t3.get())
    t1.focus()

def out(event):
    relist(t1.get(), t2.get(), t3.get())
    print '\n'.join(selectlist)
    sys.exit(0)

t1.bind("<Tab>", t1_callback)
t2.bind("<Tab>", t2_callback)
t3.bind("<Tab>", t3_callback)
t1.bind("<Return>", out)
t2.bind("<Return>", out)
t3.bind("<Return>", out)

for dirpath, dirs, files in os.walk('.'):
    allfiles.extend([os.path.join(dirpath, f) for f in files])
allfiles.sort()

for f in allfiles:
    lb.insert(END, f)
lb.config(height=min(40, len(allfiles) / 2))
t1.focus()
selectlist = allfiles

root.mainloop()
root.resizeable(width=True, height=True)
print selectlist

