class Foo<T> {
    public Foo() { }
}

class Main {
    public static void main(String[] args) {
        Foo<String> f = new Foo<String>();
        System.out.println("ok");
    }
}

