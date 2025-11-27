package java.lang;

// NeOak stdlib stub for IDEs. Implementation is provided by the runtime shim and transpiler rewrites.
public final class System {
    public static PrintStream out;
    public static PrintStream err;
    public static InputStream in;

    public static long currentTimeMillis() { return 0; }
    public static long nanoTime() { return 0; }

    public static class PrintStream {
        public void println(String s) {}
        public void println(int v) {}
        public void println(double v) {}
        public void println(boolean v) {}
        public void println(Object o) {}
        public void print(String s) {}
        public void print(int v) {}
        public void print(double v) {}
        public void print(boolean v) {}
        public void print(Object o) {}
    }

    public static class InputStream {}
}

