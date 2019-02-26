from celery import task
# 要有url，HTML页面，send_mail 缓存：key uuid value user_id
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader
from django.core.cache import caches

# 获得缓存
cache = caches['confirm']


@task
def send_verify_mail(url, user_id, reciever):
    title = "红浪漫"
    content = ""
    # 加载页面
    template = loader.get_template("user/email.html")
    # 渲染
    html = template.render({"url": url})

    email_from = settings.DEFAULT_FROM_EMAIL

    # 发送邮件
    send_mail(title, content, email_from, [reciever], html_message=html)

    # 设置缓存
    cache.set(url.split("/")[-1], user_id, settings.VERIFY_CODE_MAX_AGE)
# @task
# def send_verify_mail(url,user_id,reciever):
#     title = "hahh"
#     content = ""
#     template = loader.get_template("user/email.html")
#     html = template.render({"url":url})
#     email_from = settings.DEFAULT_FROM_EMAIL
#     send_mail(title,content,email_from,[reciever],html_message=html)
#     cache.set(url.split("/")[-1],user_id,settings.VERIFY_CODE_MAX_AGE)

