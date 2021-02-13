public class BackwardSlicerExample1{

    public static void main(String args[]){
        System.out.println("BackwardSlicerExample1");
        if (args.length < 1){
            System.out.println("Use: java -jar BackwardSlicerExample1 <STRING>");
            System.exit(1);
        }
        String x = args[0];
        func(x);
        useless(x);
        System.out.println("Done"); 
    }

    public static void func(String param){
        MyClass c = new MyClass(param + "test");
        String asd = c.append(c.field, "suffix");
        dosomething(asd);
    }

    public static void useless(String param){
        System.out.println(param);
    }

    public static void dosomething(String param){
        String local = "localString" + param;
        System.out.println(local);
    }
}
