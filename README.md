# Create a mod
无论是谁都能创建自己的MC模组！目前支持在Mac上写Fabric 1.20.6模组。不需要任何Java基础，只要写几个JSON就能实现！

**本项目仍在开发中，但部分功能已经可用！** ~~但最近AI时段用量老是触顶，可能写的有点慢~~

因为还在开发，文档写的有点潦草，请见谅。

### 创建模组
1. 用终端`cd`到一个文件夹中，确保你记得住路径。
2. 在这个目录下克隆此仓库。
3. 在你的`.zshrc`文件中添加这样一行：
    ```bash
    alias createamod=[第1步创建的目录的绝对路径]/create-a-mod/createamod.sh
    ```
4. 在终端输入：
  ```bash
  chmod +x createamod
  createamod new -mcv [你模组适配的MC版本] [你模组的名字]
  ```
5. `cd`刚才指令中输入的你模组的名字。
6. 接下来你需要自己写JSON。具体可以参考`../create-a-mod/examples/*`
