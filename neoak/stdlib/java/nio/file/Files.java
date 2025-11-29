package java.nio.file;

// NeOak stdlib stub for IDEs. Runtime behavior provided by neoak.rt.
public final class Files {
    private Files() {}

    public static boolean exists(Path p) { return false; }
    public static boolean isDirectory(Path p) { return false; }
    public static boolean isRegularFile(Path p) { return false; }
    public static String readString(Path p) { return ""; }
    public static Path writeString(Path p, String s) { return p; }
    public static void createDirectories(Path p) {}
}

