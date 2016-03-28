class PhorthError(Exception):
    """Errors raised by phorth that are non-fatal.
    """


class BadWord(PhorthError):
    """Marks that there is an error with a word read from stdin.

    Parameters
    ----------
    word : str
        The name of the word.
    file : str
        The name of the file.
    lno : int
        The line number of the error.
    col : int
        The column offset of the error.
    """
    def __init__(self, word, file, lno, col):
        self.word = word
        self.file = file
        self.lno = lno
        self.col = col

    def __str__(self):
        return 'bad word %r at %s:%d:%d' % (
            self.file,
            self.word,
            self.lno,
            self.col,
        )


class UnknownWord(BadWord):
    """Marks that a word was read in immediate mode without being defined
    ahead of time.

    Parameters
    ----------
    word : str
        The name of the word.
    file : str
        The name of the file.
    lno : int
        The line number of the error.
    col : int
        The column offset of the error.
    """
    def __str__(self):
        return 'unknown word %r at %s:%d:%d' % (
            self.word,
            self.file,
            self.lno,
            self.col,
        )


class Underflow(PhorthError):
    """Marks that there was a stack underflow.

    Parameters
    ----------
    file : str
        The name of the file.
    lno : int
        The line number of the error.
    col : int
        The column offset of the error.
    """
    def __init__(self, file, lno, col):
        self.file = file
        self.lno = lno
        self.col = col

    def __str__(self):
        return 'stack underflow at %s:%d:%d' % (self.file, self.lno, self.col)


class InvalidWordUsage(BadWord):
    """Marks that a particular word was used incorrecly.

    Parameters
    ----------
    word : str
        The name of the word.
    file : str
        The name of the file.
    lno : int
        The line number of the error.
    col : int
        The column offset of the error.
    msg : str
        The message that describes how the word was used incorrectly.
    """
    def __init__(self, word, file, lno, col, msg):
        super().__init__(word, file, lno, col)
        self.msg = msg

    def __str__(self):
        return 'invalid usage of %r at %s:%d:%d: %s' % (
            self.word,
            self.file,
            self.lno,
            self.col,
            self.msg,
        )
