package app;
class Person {
    String name;
    int age = 0;


    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String describe() {
        return this.name + ", " + this.age;
    }

    public String describe(String prefix) {
        return prefix + ": " + this.name + ", " + this.age;
    }
}

