import sys,os,shutil,json,re,subprocess,openpyxl
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog,QMessageBox
from PyQt5 import uic, QtCore
from PyQt5.QtCore import QThread, pyqtSignal, QCoreApplication
import pandas as pd
from PyQt5.QtGui import QIcon
from dcm2bids.utils import DEFAULT, assert_dirs_empty
import argparse
import logging
from pathlib import Path
import platform
from datetime import datetime
from glob import glob
from dcm2bids.dcm2niix import Dcm2niix
from dcm2bids.logger import setup_logging
from dcm2bids.sidecar import Sidecar, SidecarPairing
from dcm2bids.structure import Participant
from dcm2bids.utils import (DEFAULT, load_json, save_json,
                            splitext_, run_shell_command, valid_path)
from dcm2bids.version import __version__, check_latest, dcm2niix_version

class MainWindow(QMainWindow):
    # 加载ui,设置点击事件
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi("dcm.ui")
        self.ui.pBar.setVisible(False)

        self.ui.select_1.clicked.connect(self.handleDirectorySelection_1)
        self.ui.select_2.clicked.connect(self.handleDirectorySelection_2)
        self.ui.select_4.clicked.connect(self.handleDirectorySelection_3)
        self.ui.select_3.clicked.connect(self.builtconfigfile)
        self.ui.select_3.clicked.connect(self.show_seriesdescriptions)
        self.ui.pushButton.clicked.connect(self.mergecontent)
        self.ui.pushButton_2.clicked.connect(self.save_to_configfile)
        self.ui.pushButton_2.clicked.connect(self.runthread)
        self.ui.comboBox_2.currentIndexChanged.connect(self.update_comboBox_3)


    # 选择目录
    def handleDirectorySelection_1(self):
        directory = QFileDialog.getExistingDirectory(
            self.ui, "选择输出目录", ".", QFileDialog.ShowDirsOnly
        )
        if directory:
            self.ui.location_1.setText(directory)

        global directorytext_1
        directorytext_1 = self.ui.location_1.text()


    # 选择输入数据目录
    def handleDirectorySelection_2(self):
        directory = QFileDialog.getExistingDirectory(
            self.ui, "选择源数据", ".", QFileDialog.ShowDirsOnly
        )
        if directory:
            self.ui.location_2.setText(directory)

        global directorytext_2
        directorytext_2 = self.ui.location_2.text()


    #选择被试ID对应表
    def handleDirectorySelection_3(self):
        # 显示文件选择对话框
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(self, "选择Excel文件", "", "Excel (*.xlsx)",
                                                   options=options)

        # 更新文件路径输入框
        if file_name:
            self.ui.location_3.setText(file_name)

        global directorytext_3
        directorytext_3 = self.ui.location_3.text()


    #新建配置文件
    def builtconfigfile(self):
        text_1 = self.ui.location_1.text()
        text_2 = self.ui.location_2.text()
        if text_1 == '' or text_2 == '':
            QMessageBox.warning(self, '提示', '必选项未选择')
        else:
            filename = "dcm2bids_config.json"
            filepath = os.path.join(directorytext_1, filename)
            content = """{
              "descriptions": [
              ]
            }"""
            # 打开文件并写入内容
            with open(filepath, "w") as file:
                file.write(content)


    def show_seriesdescriptions(self):
        text_1 = self.ui.location_1.text()
        text_2 = self.ui.location_2.text()
        if text_1 == '' or text_2 == '':
            return
        else:
            self.ui.select_3.setEnabled(False)
            self.ui.select_3.setText('正在扫描...')
            QApplication.processEvents()

            self.thread = scanThread()
            self.thread.update_description.connect(self.update_series_description)
            self.thread.update_scan.connect(self.update_scan_str)
            self.thread.start()


    def mergecontent(self):
        self.ui.label_5.setVisible(False)
        QApplication.processEvents()
        # 获取三个下拉框的内容
        text1 = self.ui.comboBox_1.currentText()
        text2 = self.ui.comboBox_2.currentText()
        text3 = self.ui.comboBox_3.currentText()
        # 如果文本为空
        if not text1:
            # 弹出提示窗口
            QMessageBox.information(self, '提示', '序列描述为空，请先扫描数据')
        else:
            # 拼接成一行文本
            text = f"{text1}_{text2}_{text3}\n"
            self.ui.textBrowser.append(text)


    def save_to_configfile(self):
        self.config = {"descriptions": []}
        text=self.ui.textBrowser.toPlainText()
        if not text:
            # 弹出提示窗口
            QMessageBox.information(self, '错误提示', '请先扫描数据和配置结构文件')
        else:
            lines = text.split('\n')
            # 遍历每一行并添加到配置对象中
            for line in lines:
                if line.strip() == '':
                    continue
                # 去除序号和空格，只保留字段内容
                line = re.sub(r'^\d+\.', '', line)
                fields = line.split('_')
                dataType = fields[1]
                modalityLabel = fields[2]
                seriesDescription = fields[0]
                criteria = {"SeriesDescription": f"*{seriesDescription}*"}
                entry = {"dataType": dataType, "modalityLabel": modalityLabel, "criteria": criteria}
                self.config["descriptions"].append(entry)

            filepath1 = os.path.join(directorytext_1,'dcm2bids_config.json')
            # 将配置对象写入文件
            with open(filepath1, 'w') as f:
                json.dump(self.config, f, indent=2)


    def runbids(self):
        text_big = self.ui.textBrowser.toPlainText()
        if not text_big:
            return
        else:
            self.ui.label_5.setVisible(True)
            self.ui.pBar.setVisible(True)
            self.ui.pBar.setValue(0)
            self.ui.pushButton_2.setEnabled(False)

            sourcefile = directorytext_2
            configfile = os.path.join(directorytext_1,'dcm2bids_config.json')
            # 获取源文件夹列表
            folders = os.listdir(sourcefile)
            total = len(folders)
            self.ui.label_5.setText('正在准备开始处理任务')
            QApplication.processEvents()
            processed = 0
            subnum = 1
            row1 = 1

            # 创建Excel工作簿和工作表
            workbook = openpyxl.Workbook()
            worksheet = workbook.active
            worksheet.title = '参数记录'

            excel_path=self.ui.location_3.text()
            if not excel_path:
                worksheet.cell(row=1, column=1).value = '被试ID'
                worksheet.cell(row=1, column=2).value = '被试名'
                worksheet.cell(row=1, column=3).value = '扫描次数'
            else:
                wb = openpyxl.load_workbook(excel_path)
                sheet = wb.active
                lines = sheet.iter_rows()
                for line in lines:
                    newRow = [cell.value for cell in line]
                    worksheet.append(newRow)
                df = pd.read_excel(excel_path)
                max_id = df['被试ID'].max()
                subnum = max_id + 1
                row1 = max_id+1

            for folder in folders:
                if not excel_path:
                    command = 'dcm2bids -d %s -p %04d -s 01 -c %s -o %s' % (os.path.join(sourcefile, folder), subnum, configfile, directorytext_1)
                    os.system(command)
                    row1 = row1 + 1
                    worksheet.cell(row=row1, column=1).value = str(subnum).zfill(4)
                    worksheet.cell(row=row1, column=2).value = folder
                    worksheet.cell(row=row1, column=3).value = str(1).zfill(2)
                    subnum += 1
                else:
                    tem = None
                    df = pd.read_excel(excel_path)
                    for index, rline in df.iterrows():
                        if rline['被试名'] == folder:
                            tem = rline['被试ID']
                            break
                    if tem is not None:  # 如果tem不为None，则说明找到了一致的被试名
                        temp_df = df[df['被试ID'] == tem]
                        scannum = int(temp_df['扫描次数'].max())+1
                        if scannum > 99:
                            raise Exception("扫描次数超过99")
                        command = 'dcm2bids -d %s -p %04d -s %02d -c %s -o %s' % (os.path.join(sourcefile, folder), tem, scannum, configfile, directorytext_1)
                        os.system(command)
                        row1 = row1 + 1
                        worksheet.cell(row=row1, column=1).value = str(tem).zfill(4)
                        worksheet.cell(row=row1, column=2).value = folder
                        worksheet.cell(row=row1, column=3).value = str(scannum).zfill(2)

                    else:  # 没有一致的被试名
                        command = 'dcm2bids -d %s -p %04d -s 01 -c %s -o %s' % (os.path.join(sourcefile, folder), subnum, configfile, directorytext_1)
                        os.system(command)
                        row1 = row1 + 1
                        worksheet.cell(row=row1, column=1).value = str(subnum).zfill(4)
                        worksheet.cell(row=row1, column=2).value = folder
                        worksheet.cell(row=row1, column=3).value = str(1).zfill(2)
                        subnum += 1

                if subnum > 9999:
                    raise Exception("被试数量超过9999")

                processed += 1
                progress = int(processed / total * 100)
                self.ui.pBar.setValue(progress)
                self.ui.label_5.setText('已处理%s个任务/共%s个任务'%(processed,total))
                QCoreApplication.processEvents()

            excel_file = os.path.join(directorytext_1, '被试ID对应表.xlsx')
            workbook.save(excel_file)
            #删除配置结构文件和临时文件
            os.remove(configfile)
            tmp_dcm2bids_path = os.path.join(directorytext_1, "tmp_dcm2bids")
            shutil.rmtree(tmp_dcm2bids_path)
            # 更新标签
            self.ui.label_5.setText('处理完成')
            self.ui.pushButton_2.setEnabled(True)


    def update_comboBox_3(self):
        self.ui.comboBox_3.clear()
        # 根据comboBox_2的选项添加comboBox_3的选项
        if self.ui.comboBox_2.currentText() == "anat":
            self.ui.comboBox_3.addItem("T1w")
            self.ui.comboBox_3.addItem("T2w")
            self.ui.comboBox_3.addItem("FLAIR")
            self.ui.comboBox_3.addItem("T2starw")
        elif self.ui.comboBox_2.currentText() == "func":
            self.ui.comboBox_3.addItem("bold")
            self.ui.comboBox_3.addItem("cbv")
            self.ui.comboBox_3.addItem("phase")
        elif self.ui.comboBox_2.currentText() == "dwi":
            self.ui.comboBox_3.addItem("dwi")
            self.ui.comboBox_3.addItem("sbref")
        elif self.ui.comboBox_2.currentText() == "perf":
            self.ui.comboBox_3.addItem("asl")
            self.ui.comboBox_3.addItem("m0scan")
        elif self.ui.comboBox_2.currentText() == "fmap":
            self.ui.comboBox_3.addItem("epi")
            self.ui.comboBox_3.addItem("fieldmap")
            self.ui.comboBox_3.addItem("magnitude")
            self.ui.comboBox_3.addItem("magnitude1")
            self.ui.comboBox_3.addItem("magnitude2")
            self.ui.comboBox_3.addItem("phase1")
            self.ui.comboBox_3.addItem("phase2")
            self.ui.comboBox_3.addItem("phasediff")
        elif self.ui.comboBox_2.currentText() == "pet":
            self.ui.comboBox_3.addItem("pet")


    def runthread(self):
        text_big = self.ui.textBrowser.toPlainText()
        if not text_big:
            return
        else:
            self.ui.label_5.setVisible(True)
            self.ui.pBar.setVisible(True)
            self.ui.pBar.setValue(0)
            self.ui.pushButton_2.setEnabled(False)
            self.ui.pushButton.setEnabled(False)
            self.ui.select_3.setEnabled(False)
            self.ui.label_5.setText('正在准备开始处理任务...')
            QApplication.processEvents()

            global excel_path
            excel_path = self.ui.location_3.text()

            self.thread = MyThread()
            self.thread.update_progress.connect(self.update_bar)
            self.thread.update_l.connect(self.update_label)
            self.thread.start()


    @QtCore.pyqtSlot(int)
    def update_bar(self, progress):
        self.ui.pBar.setValue(progress)
        QCoreApplication.processEvents()


    @QtCore.pyqtSlot(int,int)
    def update_label(self,processed,total):
        self.ui.label_5.setText('已处理%s个任务/共%s个任务' % (processed, total))
        if processed == total:
            # 更新标签
            self.ui.label_5.setText('处理完成')
            self.ui.pushButton_2.setEnabled(True)
            self.ui.pushButton.setEnabled(True)
            self.ui.select_3.setEnabled(True)
        QCoreApplication.processEvents()


    @QtCore.pyqtSlot(str)
    def update_series_description(self, series_description):
        self.ui.comboBox_1.addItem(series_description)
        QCoreApplication.processEvents()


    @QtCore.pyqtSlot(int)
    def update_scan_str(self, rate):
        if rate == 1:
            self.ui.select_3.setText('扫描完成')
            self.ui.select_3.setEnabled(True)
            QApplication.processEvents()


class MyThread(QThread):
    update_progress = pyqtSignal(int)
    update_l = pyqtSignal(int,int)

    def run(self):
        sourcefile = directorytext_2
        configfile = os.path.join(directorytext_1, 'dcm2bids_config.json')
        # 获取源文件夹列表
        folders = os.listdir(sourcefile)
        total = len(folders)
        processed = 0
        subnum = 1
        row1 = 1

        # 创建Excel工作簿和工作表
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = '参数记录'

        if not excel_path:
            worksheet.cell(row=1, column=1).value = '被试ID'
            worksheet.cell(row=1, column=2).value = '被试名'
            worksheet.cell(row=1, column=3).value = '扫描次数'
        else:
            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active
            lines = sheet.iter_rows()
            for line in lines:
                newRow = [cell.value for cell in line]
                worksheet.append(newRow)
            df = pd.read_excel(excel_path)
            max_id = df['被试ID'].max()
            subnum = max_id + 1
            row1 = max_id + 1

        for folder in folders:
            if not excel_path:
                ter_run(os.path.join(sourcefile, folder),'{:04d}'.format(subnum),'{:02d}'.format(1), configfile,directorytext_1)
                row1 = row1 + 1
                worksheet.cell(row=row1, column=1).value = str(subnum).zfill(4)
                worksheet.cell(row=row1, column=2).value = folder
                worksheet.cell(row=row1, column=3).value = str(1).zfill(2)
                subnum += 1
            else:
                tem = None
                df = pd.read_excel(excel_path)
                for index, rline in df.iterrows():
                    if rline['被试名'] == folder:
                        tem = rline['被试ID']
                        break
                if tem is not None:  # 如果tem不为None，则说明找到了一致的被试名
                    temp_df = df[df['被试ID'] == tem]
                    scannum = int(temp_df['扫描次数'].max()) + 1
                    if scannum > 99:
                        raise Exception("扫描次数超过99")
                    ter_run(os.path.join(sourcefile, folder), '{:04d}'.format(tem), '{:02d}'.format(scannum), configfile,directorytext_1)
                    row1 = row1 + 1
                    worksheet.cell(row=row1, column=1).value = str(tem).zfill(4)
                    worksheet.cell(row=row1, column=2).value = folder
                    worksheet.cell(row=row1, column=3).value = str(scannum).zfill(2)

                else:  # 没有一致的被试名
                    ter_run(os.path.join(sourcefile, folder), '{:04d}'.format(subnum), '{:02d}'.format(1),configfile, directorytext_1)
                    row1 = row1 + 1
                    worksheet.cell(row=row1, column=1).value = str(subnum).zfill(4)
                    worksheet.cell(row=row1, column=2).value = folder
                    worksheet.cell(row=row1, column=3).value = str(1).zfill(2)
                    subnum += 1

            if subnum > 9999:
                raise Exception("被试数量超过9999")

            processed += 1
            progress = int((processed / total * 100)-0.01)
            self.update_progress.emit(progress)
            self.update_l.emit(processed, total)


        excel_file = os.path.join(directorytext_1, '被试ID对应表.xlsx')
        workbook.save(excel_file)
        # 删除配置结构文件和临时文件
        os.remove(configfile)
        tmp_dcm2bids_path = os.path.join(directorytext_1, "tmp_dcm2bids")
        shutil.rmtree(tmp_dcm2bids_path)
        self.update_progress.emit(100)


class scanThread(QThread):
    update_description = pyqtSignal(str)
    update_scan = pyqtSignal(int)

    def run(self):
        folders = [f for f in os.listdir(directorytext_2) if os.path.isdir(os.path.join(directorytext_2, f))]
        if len(folders) > 0:
            first_folder = folders[0]
        else:
            print('源文件中没有文件')
            exit()
        # 构造源目录下第一个文件夹的路径
        src_path = os.path.join(directorytext_2, first_folder)
        log_text = tem_run(src_path, directorytext_1)
        os.makedirs(os.path.join(directorytext_1,'log'))
        output_path=os.path.join(directorytext_1,'log','扫描日志.txt')
        with open(output_path, 'a') as f:
            f.write(log_text)

        dir_path = os.path.join(directorytext_1, 'tmp_dcm2bids', 'helper')
        # 遍历目录下的所有JSON文件，获取SeriesDescription字段的值
        for filename in os.listdir(dir_path):
            if filename.endswith('.json'):
                filepath = os.path.join(dir_path, filename)
                with open(filepath) as f:
                    data = json.load(f)
                    series_description = data['SeriesDescription']
                    self.update_description.emit(series_description)
        rate=1
        self.update_scan.emit(rate)


def _build_arg_parser():
    p = argparse.ArgumentParser(description=__doc__, epilog=DEFAULT.EPILOG,
                                formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("-d", "--dicom_dir",
                   type=Path,
                   required=True, nargs="+",
                   help="DICOM files directory.")

    p.add_argument("-o", "--output_dir",
                   required=False, default=Path.cwd(),
                   type=Path,
                   help="Output BIDS directory. "
                        "(Default: %(default)s)")

    p.add_argument('--force',
                   dest='overwrite', action='store_true',
                   help='Force command to overwrite existing output files.')

    return p


def tem_run(dicom_dir, output_dir):
    parser = _build_arg_parser()
    args = parser.parse_args(["-d", str(dicom_dir), "-o", str(output_dir)])
    out_folder = args.output_dir / DEFAULT.tmpDirName / DEFAULT.helperDir
    assert_dirs_empty(parser, args, out_folder)
    app = Dcm2niix(dicomDirs=args.dicom_dir, bidsDir=args.output_dir)
    rsl = app.run()
    return f"Example in: {out_folder}\n{rsl}"


class Dcm2bids(object):
    def __init__(
        self,
        dicom_dir,
        participant,
        config,
        output_dir=DEFAULT.outputDir,
        session=DEFAULT.session,
        clobber=DEFAULT.clobber,
        forceDcm2niix=DEFAULT.forceDcm2niix,
        log_level=DEFAULT.logLevel,
        **_
    ):
        self._dicomDirs = []

        self.dicomDirs = dicom_dir
        self.bidsDir = valid_path(output_dir, type="folder")
        self.config = load_json(valid_path(config, type="file"))
        self.participant = Participant(participant, session)
        self.clobber = clobber
        self.forceDcm2niix = forceDcm2niix
        self.logLevel = log_level

        self.set_logger()

        self.logger.info("--- dcm2bids start ---")
        self.logger.info("OS:version: %s", platform.platform())
        self.logger.info("python:version: %s", sys.version.replace("\n", ""))
        self.logger.info("dcm2bids:version: %s", __version__)
        self.logger.info("dcm2niix:version: %s", dcm2niix_version())
        self.logger.info("participant: %s", self.participant.name)
        self.logger.info("session: %s", self.participant.session)
        self.logger.info("config: %s", os.path.realpath(config))
        self.logger.info("BIDS directory: %s", os.path.realpath(output_dir))

    @property
    def dicomDirs(self):
        """List of DICOMs directories"""
        return self._dicomDirs

    @dicomDirs.setter
    def dicomDirs(self, value):

        dicom_dirs = value if isinstance(value, list) else [value]

        valid_dirs = [valid_path(_dir, "folder") for _dir in dicom_dirs]

        self._dicomDirs = valid_dirs

    def set_logger(self):
        """ Set a basic logger"""
        logDir = self.bidsDir / "log"
        logFile = logDir / f"{self.participant.prefix}_{datetime.now().isoformat().replace(':', '')}.log"
        logDir.mkdir(parents=True, exist_ok=True)

        setup_logging(self.logLevel, logFile)
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Run dcm2bids"""
        dcm2niix = Dcm2niix(
            self.dicomDirs,
            self.bidsDir,
            self.participant,
            self.config.get("dcm2niixOptions", DEFAULT.dcm2niixOptions),
        )

        check_latest()
        check_latest("dcm2niix")

        dcm2niix.run(self.forceDcm2niix)

        sidecars = []
        for filename in dcm2niix.sidecarFiles:
            sidecars.append(
                Sidecar(filename, self.config.get("compKeys", DEFAULT.compKeys))
            )

        sidecars = sorted(sidecars)

        parser = SidecarPairing(
            sidecars,
            self.config["descriptions"],
            self.config.get("searchMethod", DEFAULT.searchMethod),
            self.config.get("caseSensitive", DEFAULT.caseSensitive)
        )
        parser.build_graph()
        parser.build_acquisitions(self.participant)
        parser.find_runs()

        self.logger.info("moving acquisitions into BIDS folder")

        intendedForList = [[] for i in range(len(parser.descriptions))]
        for acq in parser.acquisitions:
            acq.setDstFile()
            intendedForList = self.move(acq, intendedForList)

    def move(self, acquisition, intendedForList):
        """Move an acquisition to BIDS format"""
        for srcFile in glob(acquisition.srcRoot + ".*"):

            ext = Path(srcFile).suffixes
            ext = [curr_ext for curr_ext in ext if curr_ext in ['.nii','.gz',
                                                                '.json',
                                                                '.bval','.bvec']]

            dstFile = (self.bidsDir / acquisition.dstRoot).with_suffix("".join(ext))

            dstFile.parent.mkdir(parents = True, exist_ok = True)

            if dstFile.exists():
                self.logger.info("'%s' already exists", dstFile)

                if self.clobber:
                    self.logger.info("Overwriting because of --clobber option")

                else:
                    self.logger.info("Use --clobber option to overwrite")
                    continue

            if (
                self.config.get("defaceTpl")
                and acquisition.dataType == "func"
                and ".nii" in ext
                ):
                try:
                    os.remove(dstFile)
                except FileNotFoundError:
                    pass
                defaceTpl = self.config.get("defaceTpl")

                cmd = [w.replace('srcFile', srcFile) for w in defaceTpl]
                cmd = [w.replace('dstFile', dstFile) for w in defaceTpl]
                run_shell_command(cmd)

                intendedForList[acquisition.indexSidecar].append(acquisition.dstIntendedFor + "".join(ext))

            elif ".json" in ext:
                data = acquisition.dstSidecarData(self.config["descriptions"],
                                                  intendedForList)
                save_json(dstFile, data)
                os.remove(srcFile)

            else:
                os.rename(srcFile, dstFile)

            intendedFile = acquisition.dstIntendedFor + ".nii.gz"
            if intendedFile not in intendedForList[acquisition.indexSidecar]:
                intendedForList[acquisition.indexSidecar].append(intendedFile)

        return intendedForList


def _build_arg_parser1():
    p = argparse.ArgumentParser(description=__doc__, epilog=DEFAULT.EPILOG,
                                formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("-d", "--dicom_dir",
                   type=Path, required=True, nargs="+",
                   help="DICOM directory(ies).")

    p.add_argument("-p", "--participant",
                   required=True,
                   help="Participant ID.")

    p.add_argument("-s", "--session",
                   required=False,
                   default="",
                   help="Session ID.")

    p.add_argument("-c", "--config",
                   type=Path,
                   required=True,
                   help="JSON configuration file (see example/config.json).")

    p.add_argument("-o", "--output_dir",
                   required=False,
                   type=Path,
                   default=Path.cwd(),
                   help="Output BIDS directory. (Default: %(default)s)")

    p.add_argument("--forceDcm2niix",
                   action="store_true",
                   help="Overwrite previous temporary dcm2niix "
                        "output if it exists.")

    p.add_argument("--clobber",
                   action="store_true",
                   help="Overwrite output if it exists.")

    p.add_argument("-l", "--log_level",
                   required=False,
                   default=DEFAULT.cliLogLevel,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                   help="Set logging level. [%(default)s]")

    return p


def ter_run(dicom_dir, participant, session, config, output_dir):
    parser = _build_arg_parser1()
    args = parser.parse_args(['-d', dicom_dir, '-p', participant, '-s', session, '-c', config, '-o', output_dir])
    obj = Dcm2bids(**vars(args))
    obj.run()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('logo.png'))
    window = MainWindow()
    window.ui.show()
    sys.exit(app.exec_())


