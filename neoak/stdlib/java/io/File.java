package java.io;

// NeOak stdlib stub for IDEs. Implementation is provided by the runtime shim (neoak.rt.File).
public class File {
    public File(String path) {}
    public boolean exists() { return false; }
    public boolean isDirectory() { return false; }
    public boolean isFile() { return false; }
    public long length() { return 0; }
    public long lastModified() { return 0; }
    public String getName() { return null; }
    public String getPath() { return null; }
    public String getAbsolutePath() { return null; }
    public boolean mkdir() { return false; }
    public boolean mkdirs() { return false; }
    public String[] list() { return null; }
    public boolean delete() { return false; }
    public String toString() { return getPath(); }
}

