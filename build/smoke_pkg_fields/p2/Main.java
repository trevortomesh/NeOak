package p2;

class Main {
    public static void main(String[] args) {
        p1.A a = new p1.A();
        System.out.println(a.x); // should be denied: different package
    }
}

