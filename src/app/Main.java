package app;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Scanner;
import java.util.NoSuchElementException;

// Sample NeOak program
class Main {
    public static void main(String[] args) {

        int[] test = {1,2,3};
        System.out.println(test[1]);
        String content = Files.readString(Paths.get("input.txt"));
        System.out.println(content);

        System.out.println("Hello from NeOak!");

        int n = 3;
        for (int i = 0; i < n; i++) {
            if (i % 2 == 0) {
                System.out.println("even:" + i);
            } else {
                System.out.println("odd:" + i);
            }
        }

        System.out.println(greet("Spabby"));

        // Arrays, foreach, ++/--, print
        int[] arr = new int[3];
        for (int i = 0; i < arr.length; i++) { arr[i] = i + 1; }
        System.out.print("arr: ");
        for (int v : arr) { System.out.print(v + ","); }
        System.out.println("");

        // Math helpers + string concat in assignment
        int a = 10; int b = 3;
        int m = Math.max(a, b);
        String msg = "max is " + m;
        System.out.println(msg);

        // Static call with class qualifier
        System.out.println(Main.greet("Neo"));

        // Instance fields + constructor + method
        Person p = new Person("Ada", 42);
        System.out.println(p.describe());

        Student s = new Student("Grace", 37, "Babbage U");
        System.out.println(s.describe());
        System.out.println(p.describe("Person"));
        System.out.println(Main.greet("Yo", 3));

        // Read input.txt with Scanner (line by line)
        Scanner sc = new Scanner("input.txt");
        try {
            while (true) {
                String line = sc.nextLine();
                System.out.println(line);
            }
        } catch (NoSuchElementException e) {
            // EOF reached
        } finally {
            sc.close();
        }
    }

    public static String greet(String name) {
        return "Hi, " + name + "!";
    }

    public static String greet(String name, int times) {
        String out = "";
        for (int i = 0; i < times; i++) { out = out + name; }
        return out;
    }
}

class Util {
    public static void demoSwitch(int v) {
        switch (v) {
            case 1:
                System.out.println("one");
                break;
            case 2:
            case 3:
                System.out.println("two or three");
                break;
            default:
                System.out.println("other");
        }
    }

    public static void demoTry(int v) {
        try {
            if (v < 0) {
                throw new RuntimeException("neg");
            }
            System.out.println("ok" + v);
        } catch (RuntimeException e) {
            System.out.println("caught:" + e);
        } finally {
            System.out.println("finally");
        }
    }
}
