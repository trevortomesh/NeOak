class Main {
    public static void main(String[] args) {
        StdDraw.open(400, 300, "NeOak Graphics");
        StdDraw.clear("white");
        StdDraw.setPenColor(255, 0, 0);
        StdDraw.line(10, 10, 390, 10);
        StdDraw.setPenColor("blue");
        StdDraw.circle(200, 150, 60);
        StdDraw.setPenColor("green");
        StdDraw.filledRectangle(150, 200, 100, 40);
        StdDraw.setPenColor("black");
        StdDraw.text(200, 150, "Hello");
        StdDraw.show();
        // Keep window responsive for a moment
        StdDraw.pause(500);
        StdDraw.close();
    }
}

