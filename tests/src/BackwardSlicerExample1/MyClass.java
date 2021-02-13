public class MyClass{
    public String field;
    public String str;

    public MyClass(String field){
        this.field = field;
    }

    public String append(String str, String suffix){
        this.str = str + suffix;
        return this.str;
    }
}
