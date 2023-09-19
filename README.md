helper.py文件更改：helper.py中包含一个_build_arg_parser函数和一个main函数，_build_arg_parser函数中定义了三个命令行参数，然后再main函数中创建命令行参数解释器并解析命令行参数。我将_build_arg_parser函数原封不动地复制到了dcm2bids_GUI.py中作为一个函数，将这里的main函数更改为tem_run普通函数并放入dcm2bids_GUI.py中，tem_run函数需要两个参数进行传递，分别是dicom_dir和output_dir，表示执行的源路径和输出路径，同时在tem_run函数内部解析命令参数的时候传入源路径和输出路径，即：args = parser.parse_args(["-d", str(dicom_dir), "-o", str(output_dir)])

dcm2bids.py文件更改：dcm2bids.py中包含一个Dcm2bids类和_build_arg_parser函数以及一个main函数，_build_arg_parser函数和helper.py中的同名函数功能一样，只是多了几个命令行参数而已，这部分是直接复制到dcm2bids_GUI.py中的，为了避免重名，函数名改为了_build_arg_parser1。Dcm2bids类也是直接复制到了dcm2bids_GUI.py中。main函数则是更改为ter_run普通函数，并且传入了五个参数：dicom_dir, participant, session, config, output_dir，同时在ter_run函数内部解析命令参数传入这几个变量，即：args = parser.parse_args(['-d', dicom_dir, '-p', participant, '-s', session, '-c', config, '-o', output_dir])

更改说明：

1.新增了备注字段，该字段根据实际需要进行输入，最后内容会写入文件名中

2.修复了因为序列描述中存在下划线时候导致识别错误的bug

3.增加一个environment.yml文件，包含源码运行所需要的库（exe可执行文件不需要）

4.打包命令：pyinstaller -F -w --hidden-import openpyxl.cell._writer D:\dcm\dcm2bidsGUI-main\dcm2bids_GUI.py
