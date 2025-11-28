class C {
    static int X = 2;
    static { System.out.println("clinit:" + X); X = X + 1; }
}

class Main {
    public static void main(String[] args) {
        System.out.println(C.X);
    }
}

