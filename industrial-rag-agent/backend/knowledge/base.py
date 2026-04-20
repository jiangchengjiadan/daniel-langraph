"""知识库模块 - 电机售后知识库初始化"""
import re
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from backend.config.settings import settings
from backend.logging.config import get_logger
from backend.models.providers import get_embeddings

logger = get_logger(__name__)


def _chroma_collection_name() -> str:
    """按 embedding 模型隔离 collection，避免不同向量维度冲突。"""
    model_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", settings.EMBEDDING_MODEL).strip("_")
    return f"motor_knowledge_{model_name or 'default'}"[:63].strip("_-")


def create_motor_knowledge_documents() -> list:
    """创建电机售后知识库文档（10条示例数据）"""

    knowledge_documents = [
        # 1. 电机产品系列与规格参数
        Document(
            page_content="""电机产品系列与规格参数：

Y系列三相异步电动机是我公司主打产品，广泛应用于工业传动设备。

主要规格参数：
- 功率范围：0.75kW ~ 315kW
- 极数：2极、4极、6极、8极
- 额定电压：380V（可定制220V/660V）
- 额定频率：50Hz（可定制60Hz）
- 防护等级：IP55（标准）、IP65（可选）
- 冷却方式：IC411自扇冷

典型型号示例：
- Y160M-4：7.5kW，4极，1450rpm
- Y200L-4：30kW，4极，1470rpm
- Y280S-4：75kW，4极，1480rpm

安装方式：B3（底脚安装）、B5（法兰安装）、B35（底脚+法兰）""",
            metadata={"source": "product_specs.pdf", "category": "产品规格"},
        ),
        # 2. 电机安装与调试指南
        Document(
            page_content="""电机安装与调试指南：

一、安装前检查：
1. 核对电机型号、功率、电压是否与设计一致
2. 检查电机外观是否有运输损坏
3. 用500V兆欧表测量绝缘电阻，应大于0.5MΩ
4. 手动盘车检查转子是否灵活，无卡滞现象

二、安装要求：
1. 安装基础应平整、坚固，平面度误差≤0.5mm/m
2. 底脚螺栓应均匀拧紧，扭矩符合标准
3. 电机轴线与负载轴线应对中，误差≤0.05mm
4. 通风口应保持清洁，间距≥100mm

三、调试步骤：
1. 空载试运行30分钟，监测电流、温升
2. 空载电流应为额定电流的20-40%
3. 轴承温度不应超过70℃，温升不超过40K
4. 运行平稳，无异常振动和噪声

四、注意事项：
- 禁止反接制动
- 变频器供电时需设置合适的V/F曲线
- 定期检查接线端子紧固情况""",
            metadata={"source": "installation_guide.pdf", "category": "安装调试"},
        ),
        # 3. 电机无法启动故障排查
        Document(
            page_content="""电机无法启动故障排查指南：

一、电源问题（最常见）：
1. 检查电源电压是否正常（380V±10%）
2. 检查三相电压是否平衡，偏差≤5%
3. 检查熔断器是否熔断
4. 检查接触器线圈是否烧毁
5. 检查热继电器是否动作跳闸

二、电机本体问题：
1. 测量定子绕组直流电阻，三相偏差≤2%
2. 用兆欧表测量对地绝缘电阻，应＞0.5MΩ
3. 检查轴承是否卡死
4. 检查负载是否卡死或过载

三、控制线路问题：
1. 检查启动按钮是否接触良好
2. 检查停止按钮是否复位
3. 检查控制回路保险丝
4. 检查PLC输出点或变频器故障

四、典型故障代码：
- E001：电源缺相
- E002：电机过载
- E003：接地故障
- E004：变频器过流

排查建议：先查电源，再查控制，最后查电机本体。""",
            metadata={"source": "troubleshooting.pdf", "category": "故障排查"},
        ),
        # 4. 电机过热原因分析
        Document(
            page_content="""电机过热原因分析与处理：

电机温升标准：绝缘等级B级允许温升80K，F级允许105K，H级允许125K。

一、过载原因：
1. 负载超过额定值，检查负载电流
2. 电压过高或过低（±10%范围内）
3. 通风道堵塞，清理通风口
4. 环境温度过高（＞40℃需降容使用）

二、散热不良：
1. 风扇损坏或脱落，检查风扇状态
2. 通风道积灰，用压缩空气清理
3. 环境温度过高，改善通风条件
4. 阳光直射，加装遮阳棚

三、电气故障：
1. 定子绕组匝间短路，测量直流电阻
2. 转子断条，测量转子电流波形
3. 轴承损坏，检查轴承温度和振动
4. 电源缺相运行，检查三相电流平衡

四、处理措施：
- 立即停机检查，防止烧毁绕组
- 安装温度保护装置（Pt100热电阻）
- 定期巡检，记录温度数据
- 夏季高温期间加强监控""",
            metadata={"source": "overheat_analysis.pdf", "category": "故障排查"},
        ),
        # 5. 电机振动异常处理
        Document(
            page_content="""电机振动异常处理指南：

振动标准：GB 10068-2008
- 转速3000rpm：振动速度≤4.5mm/s
- 转速1500rpm：振动速度≤3.5mm/s
- 转速1000rpm：振动速度≤2.8mm/s
- 转速750rpm及以下：振动速度≤2.0mm/s

一、振动原因分类：

机械类（占70%）：
1. 不对中：联轴器偏移≤0.05mm
2. 不平衡：做动平衡校正
3. 轴承损坏：更换轴承
4. 地脚松动：紧固螺栓

电气类（占20%）：
1. 气隙不均匀：调整定子位置
2. 转子断条：检查转子电流
3. 电源频率偏差：检查变频器参数

其他类（占10%）：
1. 负载共振：改变转速
2. 基础共振：加固基础

二、振动分析方法：
- 时域波形：判断冲击特征
- 频谱分析：识别故障频率
- 轴承包络：检测轴承早期故障

三、处理建议：
1. 用振动分析仪检测各点数据
2. 对比历史数据判断发展趋势
3. 制定维修计划""",
            metadata={"source": "vibration_analysis.pdf", "category": "故障排查"},
        ),
        # 6. 电机日常维护保养规范
        Document(
            page_content="""电机日常维护保养规范：

一、日常检查（每日）：
1. 检查运行电流，不应超过额定值
2. 检查轴承温度，≤70℃
3. 听运行声音，有无异常噪声
4. 检查外壳温度，正常≤80℃

二、定期维护（每月）：
1. 清洁电机外壳和通风口
2. 检查接线端子紧固程度
3. 检查接地线连接可靠
4. 检查密封件是否老化

三、润滑管理（每3个月）：
1. 轴承润滑脂添加量：
   - 2极电机：腔体1/3
   - 4极及以上：腔体1/2
2. 推荐润滑脂：锂基脂2#
3. 更换周期：一般2年或5000小时
4. 禁止混合不同品牌润滑脂

四、定期检修（每年）：
1. 测量绝缘电阻
2. 检查绕组状态
3. 检查轴承间隙
4. 检查端盖磨损

五、注意事项：
- 停电后5分钟方可操作
- 禁止用水冲洗电机
- 记录维护数据便于趋势分析""",
            metadata={"source": "maintenance.pdf", "category": "维护保养"},
        ),
        # 7. 变频器故障代码解读
        Document(
            page_content="""变频器常见故障代码解读：

一、过流类故障：
OC1：加速时过电流
  - 原因：加速时间过短、电机堵转
  - 处理：延长加速时间、检查负载

OC2：减速时过电流
  - 原因：减速时间过短、负载惯性大
  - 处理：延长减速时间、加制动电阻

OC3：恒速时过电流
  - 原因：负载突变、电机故障
  - 处理：检查负载、检查电机

二、过压类故障：
OV1：加速时过电压
OV2：减速时过电压
OV3：恒速时过电压
  - 原因：输入电压过高、制动不及时
  - 处理：检查输入电压、调整制动参数

三、欠压类故障：
LV：母线电压过低
  - 原因：输入电压不足、缺相
  - 处理：检查输入电源、检查熔断器

四、其他故障：
OH：变频器过热 → 检查风扇、清理散热片
EF：接地故障 → 检查电机绝缘
CPF：控制电路故障 → 联系厂家

故障复位方法：按RESET键或断电重启""",
            metadata={"source": "vfd_codes.pdf", "category": "故障代码"},
        ),
        # 8. 电机轴承更换指南
        Document(
            page_content="""电机轴承更换指南：

一、准备工作：
1. 准备同型号新轴承
2. 准备拉马、铜棒、加热器等工具
3. 准备清洁用品（煤油、棉布）
4. 断电挂牌，确认安全

二、拆卸步骤：
1. 拆除电机端盖
2. 用拉马均匀用力拉出旧轴承
3. 禁止直接敲击轴承外圈
4. 清理轴颈和端盖轴承室

三、安装步骤：
1. 检查新轴承型号正确
2. 用加热器将轴承加热至80-100℃
3. 快速套入轴颈，自然冷却
4. 禁止直接敲击安装

四、注意事项：
1. 加热温度不超过120℃，禁止明火
2. 轴承必须平行装入，避免倾斜
3. 保持清洁，禁止杂物进入
4. 润滑脂填充量适量

五、装配后检查：
1. 手动盘车灵活无卡滞
2. 测量轴承间隙符合要求
3. 空载试运行2小时无异常

轴承型号示例：
- Y160M：6208-2RS（深沟球轴承）
- Y200L：6312-2RS
- Y280S：6316-2RS""",
            metadata={"source": "bearing_replacement.pdf", "category": "配件更换"},
        ),
        # 9. 产品保修条款与流程
        Document(
            page_content="""产品保修条款与保修流程：

一、保修期限：
1. 电机整机保修期：18个月
2. 从出厂日期算起
3. 易损件（轴承、风扇）保修6个月
4. 变频器保修18个月

二、保修范围：
在保修期内，以下情况免费维修：
- 制造质量问题
- 非人为损坏
- 正常使用下的故障

三、以下情况不在保修范围：
1. 用户自行拆卸、改动
2. 安装不当导致的损坏
3. 过载、缺相运行损坏
4. 自然灾害造成的损坏
5. 无购买凭证

四、保修流程：
1. 联系当地经销商或客服热线
2. 描述故障现象，提供照片/视频
3. 客服判断是否符合保修条件
4. 符合条件：上门取件或送修
5. 维修周期：7-15个工作日
6. 维修后寄回，提供维修报告

五、联系方式：
- 客服热线：400-XXX-XXXX
- 在线客服：www.example.com
- 邮箱：service@example.com

六、超保修服务：
- 提供有偿维修服务
- 可签订维保合同""",
            metadata={"source": "warranty_policy.pdf", "category": "保修政策"},
        ),
        # 10. 售后服务流程与联系方式
        Document(
            page_content="""售后服务流程与联系方式：

一、售后服务流程：

1. 咨询阶段
   - 拨打客服热线或在线提交
   - 描述问题现象
   - 客服初步判断，给出建议

2. 远程支持
   - 电话指导排查
   - 视频连线诊断
   - 大部分问题可远程解决

3. 现场服务
   - 需现场服务，预约时间
   - 工程师上门检测
   - 现场维修或更换配件

4. 跟踪回访
   - 服务完成后7天内回访
   - 确认问题解决
   - 收集改进建议

二、服务网络：
- 全国50+服务网点
- 覆盖主要工业城市
- 24小时内响应

三、备件供应：
- 原厂备件供应
- 48小时内发货
- 提供备件更换指导

四、技术培训：
- 新机操作培训
- 日常维护培训
- 故障诊断培训

五、联系渠道：
- 客服热线：400-XXX-XXXX（7×24小时）
- 在线客服：www.example.com（8:00-20:00）
- 紧急报修：189-XXXX-XXXX
- 邮箱：service@example.com

六、服务监督：
- 服务后发送满意度调查
- 投诉建议：complaint@example.com
- 48小时内回复处理""",
            metadata={"source": "service_process.pdf", "category": "售后服务"},
        ),
    ]

    return knowledge_documents


def initialize_vector_store():
    """初始化向量数据库"""
    logger.info("初始化向量数据库...")

    # 初始化嵌入模型
    embeddings = get_embeddings()

    # 创建知识库文档
    documents = create_motor_knowledge_documents()

    # 创建向量存储
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(settings.CHROMA_PERSIST_DIR),
        collection_name=_chroma_collection_name(),
    )

    # 创建检索器
    retriever = vector_store.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})

    logger.info(f"向量数据库初始化完成，文档数量：{len(documents)}")
    return retriever, vector_store


# 全局变量存储向量存储
_vector_store = None
_retriever = None


def get_retriever():
    """获取全局检索器"""
    global _vector_store, _retriever
    if _retriever is None:
        _retriever, _vector_store = initialize_vector_store()
    return _retriever


def get_vector_store():
    """获取全局向量存储"""
    global _vector_store
    if _vector_store is None:
        _, _vector_store = initialize_vector_store()
    return _vector_store
