helper.py�ļ����ģ�helper.py�а���һ��_build_arg_parser������һ��main������_build_arg_parser�����ж��������������в�����Ȼ����main�����д��������в��������������������в������ҽ�_build_arg_parser����ԭ�ⲻ���ظ��Ƶ���dcm2bids_GUI.py����Ϊһ���������������main��������Ϊtem_run��ͨ����������dcm2bids_GUI.py�У�tem_run������Ҫ�����������д��ݣ��ֱ���dicom_dir��output_dir����ʾִ�е�Դ·�������·����ͬʱ��tem_run�����ڲ��������������ʱ����Դ·�������·��������args = parser.parse_args(["-d", str(dicom_dir), "-o", str(output_dir)])

dcm2bids.py�ļ����ģ�dcm2bids.py�а���һ��Dcm2bids���_build_arg_parser�����Լ�һ��main������_build_arg_parser������helper.py�е�ͬ����������һ����ֻ�Ƕ��˼��������в������ѣ��ⲿ����ֱ�Ӹ��Ƶ�dcm2bids_GUI.py�еģ�Ϊ�˱�����������������Ϊ��_build_arg_parser1��Dcm2bids��Ҳ��ֱ�Ӹ��Ƶ���dcm2bids_GUI.py�С�main�������Ǹ���Ϊter_run��ͨ���������Ҵ��������������dicom_dir, participant, session, config, output_dir��ͬʱ��ter_run�����ڲ�����������������⼸������������args = parser.parse_args(['-d', dicom_dir, '-p', participant, '-s', session, '-c', config, '-o', output_dir])

����˵����

1.�����˱�ע�ֶΣ����ֶθ���ʵ����Ҫ�������룬������ݻ�д���ļ�����

2.�޸�����Ϊ���������д����»���ʱ����ʶ������bug

3.����һ��environment.yml�ļ�������Դ����������Ҫ�Ŀ⣨exe��ִ���ļ�����Ҫ��

4.������pyinstaller -F -w --hidden-import openpyxl.cell._writer D:\dcm\dcm2bidsGUI-main\dcm2bids_GUI.py
