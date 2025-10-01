import os
import json
import requests
from datetime import datetime
from flask import render_template, request
from run import app
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid
from wxcloudrun.model import Counters
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response


@app.route('/')
def index():
    """
    :return: 返回index页面
    """
    return render_template('index.html')


@app.route('/api/count', methods=['POST'])
def count():
    """
    :return:计数结果/清除结果
    """

    # 获取请求体参数
    params = request.get_json()

    # 检查action参数
    if 'action' not in params:
        return make_err_response('缺少action参数')

    # 按照不同的action的值，进行不同的操作
    action = params['action']

    # 执行自增操作
    if action == 'inc':
        counter = query_counterbyid(1)
        if counter is None:
            counter = Counters()
            counter.id = 1
            counter.count = 1
            counter.created_at = datetime.now()
            counter.updated_at = datetime.now()
            insert_counter(counter)
        else:
            counter.id = 1
            counter.count += 1
            counter.updated_at = datetime.now()
            update_counterbyid(counter)
        return make_succ_response(counter.count)

    # 执行清0操作
    elif action == 'clear':
        delete_counterbyid(1)
        return make_succ_empty_response()

    # action参数错误
    else:
        return make_err_response('action参数错误')


@app.route('/api/count', methods=['GET'])
def get_count():
    """
    :return: 计数的值
    """
    counter = Counters.query.filter(Counters.id == 1).first()
    return make_succ_response(0) if counter is None else make_succ_response(counter.count)

@app.route('/api/access_token', methods=['GET'])
def get_access_token():
    """
    获取微信接口的访问凭证（access_token）
    :return: 访问凭证（access_token）
    """
    # 从环境变量中获取appid和appsecret
    appid = os.environ.get('APPID')
    appsecret = os.environ.get('APPSECRET')

    # 调用微信接口获取access_token
    url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={appsecret}'
    response = requests.get(url)
    data = response.json()
    print(data,'获取access_token')

    # 从返回结果中提取access_token
    access_token = data.get('access_token')

    # 检查是否成功获取access_token
    if not access_token:
        return make_err_response('获取access_token失败')

    return access_token

@app.route('/api/add_material', methods=['POST'])
def add_material():
    """
    上传永久素材
    支持图片(image)、语音(voice)、视频(video)和缩略图(thumb)类型
    """
    try:
        # 获取媒体类型参数
        media_type = request.form.get('type')
        if not media_type or media_type not in ['image', 'voice', 'video', 'thumb']:
            return make_err_response('媒体类型参数错误，支持的类型：image, voice, video, thumb')
        
        # 检查文件是否存在
        if 'media' not in request.files:
            return make_err_response('缺少媒体文件')
        
        file = request.files['media']
        if file.filename == '':
            return make_err_response('未选择文件')
        
        # 构建请求URL
        url = f'https://api.weixin.qq.com/cgi-bin/material/add_material?type={media_type}'
        
        # 准备文件数据
        files = {'media': (file.filename, file.read(), file.mimetype)}
        
        # 准备视频素材的描述信息（如果是视频类型）
        data = None
        if media_type == 'video':
            title = request.form.get('title', '')
            introduction = request.form.get('introduction', '')
            data = {'description': json.dumps({'title': title, 'introduction': introduction})}
        
        # 调用微信接口上传素材
        response = requests.post(url, files=files, data=data)
        result = response.json()
        
        # 检查上传是否成功
        if 'errcode' in result and result['errcode'] != 0:
            return make_err_response(f'上传失败: {result.get("errmsg", "未知错误")}')
        
        # 返回成功结果
        return make_succ_response({
            'media_id': result.get('media_id'),
            'url': result.get('url')  # 仅图片素材返回
        })
        
    except Exception as e:
        print(f'上传永久素材异常: {str(e)}')
        return make_err_response(f'服务器内部错误: {str(e)}')


@app.route('/api/draft_add', methods=['POST'])
def draft_add():
    """
    新增草稿
    将常用的素材添加到微信公众号草稿箱
    支持图文消息(news)和图片消息(newspic)类型
    """
    try:
        # 获取请求体参数
        params = request.get_json()
        if not params:
            return make_err_response('请求体不能为空')
        
        # 检查articles参数
        if 'articles' not in params:
            return make_err_response('缺少articles参数')
        
        articles = params['articles']
        if not isinstance(articles, list) or len(articles) == 0:
            return make_err_response('articles必须是非空数组')
        
        # 构建请求URL
        url = f'https://api.weixin.qq.com/cgi-bin/draft/add'
        
        # 准备请求数据
        data = {'articles': articles}
        
        # 调用微信接口
        response = requests.post(url, json=data)
        result = response.json()
        
        # 检查调用是否成功
        if 'errcode' in result and result['errcode'] != 0:
            return make_err_response(f'添加草稿失败: {result.get("errmsg", "未知错误")}')
        
        # 返回成功结果
        return make_succ_response({
            'media_id': result.get('media_id'),  # 草稿ID
            'create_time': result.get('create_time')  # 创建时间
        })
        
    except Exception as e:
        print(f'新增草稿异常: {str(e)}')
        return make_err_response(f'服务器内部错误: {str(e)}')


@app.route('/api/freepublish_submit', methods=['POST'])
def freepublish_submit():
    """
    发布草稿
    将图文草稿提交发布
    需要先将图文素材以草稿的形式保存，然后选择要发布的草稿media_id进行发布
    """
    try:
        # 获取请求体参数
        params = request.get_json()
        if not params:
            return make_err_response('请求体不能为空')
        
        # 检查media_id参数
        if 'media_id' not in params:
            return make_err_response('缺少media_id参数')
        
        media_id = params['media_id']
        if not media_id:
            return make_err_response('media_id不能为空')
        
        # 构建请求URL
        url = f'https://api.weixin.qq.com/cgi-bin/freepublish/submit'
        
        # 准备请求数据
        data = {'media_id': media_id}
        
        # 调用微信接口
        response = requests.post(url, json=data)
        result = response.json()
        
        # 检查调用是否成功
        if 'errcode' in result and result['errcode'] != 0:
            return make_err_response(f'发布草稿失败: {result.get("errmsg", "未知错误")}')
        
        # 返回成功结果
        return make_succ_response({
            'publish_id': result.get('publish_id'),  # 发布任务的id
            'msg_data_id': result.get('msg_data_id')  # 消息的数据ID
        })
        
    except Exception as e:
        print(f'发布草稿异常: {str(e)}')
        return make_err_response(f'服务器内部错误: {str(e)}')
