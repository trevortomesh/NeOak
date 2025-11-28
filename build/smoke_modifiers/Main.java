class A {
    private int x;
    protected int y;
    public int z;

    public A() {
        this.x = 1;
        this.y = 2;
        this.z = 3;
    }
    private void p() { System.out.println("p"); }
    protected void q() { System.out.println("q"); }
    public void r() { System.out.println("r"); this.p(); this.q(); }
}

class B extends A {
    public void s() { System.out.println(this.y); }
}

class Main {
    public static void main(String[] args) {
        A a = new A();
        System.out.println(a.z); // ok
        a.r();                  // ok
        B b = new B();
        try {
            System.out.println(a.y); // protected access from outside: denied
        } catch (Exception e) { System.out.println("denied"); }
        try {
            System.out.println(a.x); // private access from outside: denied
        } catch (Exception e) { System.out.println("denied"); }
        b.s(); // ok: protected access within subclass
    }
}

