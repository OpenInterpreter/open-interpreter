import os
import argparse

from git import Repo

class GitPython:
    def __init__(self):
        self.repo = Repo(".")

    def add_and_commit(self, message):
        repo = self.repo
        git = repo.git
        git.add("*")
        git.commit("-m", message)

gitpython = GitPython()

def parser_gp():
    parser = argparse.ArgumentParser(description="combination and simplification of some useful git commands")
    subparser = parser.add_subparsers(help="commands")

    addc = subparser.add_parser("addc", help="add and commit")
    addc.add_argument("-m", help="commit message", required=True)

    args = parser.parse_args()
    if "m" in args:
        gitpython.add_and_commit(args.m)
    
if __name__ == "__main__":
    parser_gp()