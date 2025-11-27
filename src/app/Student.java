package app;
class Student extends Person {
    String school;

    public Student(String name, int age, String school) {
        super(name, age);
        this.school = school;
    }

    public String describe() {
        return super.describe() + ", " + this.school;
    }
}

