from phorth.core import State
from phorth.exc import PhorthError, UnknownWord
from phorth.word import words


def run_phorth(st):
    namespace = st.namespace
    push = st.push

    for name in st.iterwords():
        try:
            try:
                word = namespace[name]
            except KeyError:
                if not st.immediate:
                    push(name)
                    continue
                raise UnknownWord(name, st.file, st.lno, st.col)

            if st.immediate or word.immediate:
                word.code(st)
            else:
                push(name)

        except PhorthError as e:
            print('%s: %s' % (type(e).__name__, e))


def main():
    run_phorth(State(words()))


if __name__ == '__main__':
    main()
