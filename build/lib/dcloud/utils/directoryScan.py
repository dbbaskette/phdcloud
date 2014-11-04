__author__ = 'root'
import os,glob

def getFilename(phdPath,pattern):
    for file in glob.glob1(phdPath,pattern+"*.gz"):
        return file