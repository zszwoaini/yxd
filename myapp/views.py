from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse, HttpResponse, QueryDict
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from .my_utils import *
from .models import *
from .tasks import send_verify_mail
from django.core.cache import caches
# Create your views here.
cache = caches['confirm']

def home(req):
    wheels = Wheel.objects.all()
    menus = Nav.objects.all()
    mustbuy = MustBuy.objects.all()
    shops = Shop.objects.all()
    mainshows = MainShow.objects.all()
    result = {
        "title": "首页",
        "wheels": wheels,
        "menus": menus,
        "mustbuy": mustbuy,
        "shop0": shops[0],
        "shop1_3": shops[1:3],
        "shop3_7": shops[3:7],
        "shop_last": shops[7:],
        "mainshows": mainshows
    }

    return render(req, 'home/home.html', result)


def market(req):
    return redirect(reverse("axf:market_params", args=("104749", "0", 0)))


def market_with_params(req, type_id, sub_type_id, order_type):
    # 获取所有的一级分类
    types = FoodTypes.objects.all()

    # 获取二级分类数据
    current_cate = types.filter(typeid=type_id)[0]
    childtypenames = current_cate.childtypenames.split("#")

    sub_types = [i.split(":") for i in childtypenames]

    # 根据typeid 搜索商品信息
    goods = Goods.objects.filter(
        categoryid=int(type_id)
    )

    # 根据二级分类的id 查询商品的数据
    if sub_type_id == '0':
        pass
    else:
        goods = goods.filter(childcid=int(sub_type_id))
    user = req.user
    if isinstance(user, MyUser):
        tmp_dict = {}
        # 去购物车查该用户的商品数据
        cart_nums = Cart.objects.filter(user=user)
        for i in cart_nums:
            tmp_dict[i.goods.id] = i.num

        # tmp_dict = {i.goods.id:i.num for i in Cart.objects.filter(user=user)}
        # print(cart_nums)
        # {1245: 3}
        # print(tmp_dict)
        for i in goods:
            # 添加商品数量
            i.num = tmp_dict.get(i.id) if tmp_dict.get(i.id) else 0
            # for j in cart_nums:
            #     if i.id == j.goods_id:
            #         i.num = j.num

    # 排序
    """
    0  不排序
    1 价格
    2 销量
    """
    NO_SORT = 0
    PRICE_SORT = 1
    SALES_SORT = 2
    if int(order_type) == 0:
        pass
    elif int(order_type) == 1:
        goods = goods.order_by("price")
    else:
        goods = goods.order_by("productnum")

    result = {
        "title": "闪购",
        "types": types,
        "goods": goods,
        "current_type_id": type_id,
        "sub_types": sub_types,
        "current_sub_type_id": sub_type_id,
        "order_type": int(order_type)
    }
    return render(req, "market/market.html", result)

@login_required(login_url="/axf/login")
def cart(req):
    user = req.user
    data = Cart.objects.filter(user_id=user.id)
    sum_money = get_cart_money(data)
    if data.exists() and not data.filter(is_selected=False).exists():
        is_all_select = True
    else:
        is_all_select = False
    result = {
        "title": "购物车",
        "uname": user.username,
        "phone": user.phone if user.phone else "暂无",
        "address": user.address if user.address else "暂无",
        "cart_items": data,
        "sum_money": sum_money,
        "is_all_select": is_all_select
    }
    return render(req, "cart/cart.html", result)
def mine(req):
    btns = MineBtns.objects.filter(is_used=True)
    result = {
        "title":"我的",
        "btns":btns

    }
    return  render(req,"mine/mine.html",result)





@login_required(login_url="/axf/login")
def mine(req):
    btns = MineBtns.objects.filter(is_used=True)
    # 拿当前的用户
    user = req.user
    is_login = True
    if isinstance(user, AnonymousUser):
        is_login = False

    u_name = user.username if is_login else ""
    icon = "http://" + req.get_host() + "/static/uploads/" + user.icon.url if is_login else ""
    result = {
        "title": "我的",
        "btns": btns,
        "is_login": is_login,
        "u_name": u_name,
        "icon": icon
    }
    return render(req, "mine/mine.html", result)


class RegisterAPI(View):

    def get(self, req):
        return render(req, "user/register.html")

    def post(self, req):
        # 解析参数
        params = req.POST
        icon = req.FILES.get("u_icon")
        name = params.get("u_name")
        pwd = params.get("u_pwd")
        confirm_pwd = params.get("u_confirm_pwd")
        email = params.get("email")

        # 校验密码
        if pwd and confirm_pwd and pwd == confirm_pwd:
            # 判断用户名是否可用
            if MyUser.objects.filter(username=name).exists():
                return render(req, "user/register.html", {"help_msg": "该用户已存在"})
            else:
                user = MyUser.objects.create_user(
                    username=name,
                    password=pwd,
                    email=email,
                    is_active=False,
                    icon=icon
                )
                # 生成验证连接
                url = "http://" + req.get_host() + "/axf/confirm/" + get_unique_str()
                # 发送邮件 异步调用
                send_verify_mail.delay(url, user.id, email)
                # 设置缓存 返回登录页面
                return render(req, "user/login.html")


class LoginAPI(View):

    def get(self, req):
        return render(req, 'user/login.html')

    def post(self, req):
        # 1 解析参数
        params = req.POST
        name = params.get("name")
        pwd = params.get("pwd")
        # 2 校验数据
        if not name or not pwd:
            data = {
                "code": 2,
                "msg": "账号或密码不能为空",
                "data": ""
            }
            return JsonResponse(data)
        # 3 使用用户名 密码校验用户，
        user = authenticate(username=name, password=pwd)
        # 4 如果校验成功 登录
        if user:
            login(req, user)
            data = {
                'code': 1,
                "msg": "ok",
                "data": "/axf/mine"
            }
            return JsonResponse(data)
        # 5 失败的话返回错误提示
        else:
            data = {
                "code": 3,
                "msg": "账号或密码错误",
                "data": ""
            }
            return JsonResponse(data)


class LogoutAPI(View):

    def get(self, req):
        logout(req)
        return redirect(reverse("axf:mine"))


def confirm(req, uuid_str):
    # 1 去缓存尝试拿数据
    user_id = cache.get(uuid_str)
#   2 如果我们拿到用户id 修改is_active字段
    if user_id:
        user = MyUser.objects.get(pk=int(user_id))
        user.is_active = True
        user.save()
        return redirect(reverse("axf:login"))
#     3 如果没拿到 就返回验证失败
    else:
        return HttpResponse("<h2>链接已失效</h2>")
def check_uname(req):
    uname = req.GET.get("uname")
    data = {
        "code":1,
        "data":""

    }
    if uname and len(uname) >= 3:
        if MyUser.objects.filter(username=uname).exists():
            data["msg"] = "账号已存在"
        else:
            data["msg"] = "账号可用"
    else:
        data["msg"] = "用户名过短"
    return JsonResponse(data)

class CartAPI(View):

    def post(self, req):

        # 先看用户是否登录
        user = req.user
        if not isinstance(user, MyUser):
            data = {
                "code": 2,
                "msg": "not login",
                "data": "/axf/login"
            }
            return JsonResponse(data)

        # 拿参数
        op_type = req.POST.get("type")
        g_id = int(req.POST.get("g_id"))
        # 先获取商品数据
        goods = Goods.objects.get(pk=g_id)
        if op_type == "add":
            # 添加购物车的操作
            goods_num = 1
            if goods.storenums > 1:
                cart_goods = Cart.objects.filter(
                    user=user,
                    goods=goods
                )
                if cart_goods.exists():
            #         不是第一次添加
                    cart_item = cart_goods.first()
                    # 在原来基础上加1
                    cart_item.num = cart_item.num + 1
                    cart_item.save()
                    # 修改返回数量
                    goods_num = cart_item.num
                else:
            #         是第一次添加
                    Cart.objects.create(
                        user=user,
                        goods=goods
                    )
                data = {
                    "code": 1,
                    "msg": "ok",
                    "data": goods_num
                }
                return JsonResponse(data)
            else:
                data = {
                    "code": 3,
                    "msg": "库存不足",
                    "data": ""
                }
                return JsonResponse(data)
        elif op_type == "sub":
            goods_num = 0
            cart_item = Cart.objects.get(
                user=user,
                goods=goods
            )
            cart_item.num -= 1
            cart_item.save()
            if cart_item.num == 0:
                cart_item.delete()
            else:
                goods_num=cart_item.num
            data = {
                "code":1,
                "msg":"ok",
                "data":goods_num

            }
            return JsonResponse(data)

class CartStatusAPI(View):
    def patch(self,req):
        par = QueryDict(req.body)
        c_id = int(par.get("c_id"))
        user = req.user
        cart_items = Cart.objects.filter(user_id=user.id)
        cart_data = cart_items.get(id=c_id)
        cart_data.is_selected = not cart_data.is_selected
        cart_data.save()
        sum_money = get_cart_money(cart_items)
        if cart_items.filter(is_selected=False).exists():
            is_all_selected = False
        else:
            is_all_selected = True
        result = {
            "code":1,
            "msg":"ok",
            "data":{
                "is_select_all":is_all_selected,
                "sum_money":sum_money,
                "status":cart_data.is_selected
            }
        }
        return  JsonResponse(result)


class CartAllStatusAPI(View):

    def put(self, req):
        user = req.user

#         判断操作
        cart_items = Cart.objects.filter(user_id=user.id)
        is_select_all = False
        if cart_items.exists() and cart_items.filter(is_selected=False).exists():
            is_select_all = True
#             由于当前处于未全选的状态 那么我们需要做的操作就是将所有的未选中的商品 状态置反
#             for i in cart_items.filter(is_selected=False):
#                 i.is_selected = True
#                 i.save()
#             将未选中的数据 变成选中状态
            cart_items.filter(is_selected=False).update(is_selected=True)
            # 算钱
            sum_money = get_cart_money(cart_items)
        else:
            # 将所有选中的商品状态取反
            cart_items.update(is_selected=False)
            # 由于已经是全不选的状态 所以钱数是0
            sum_money = 0

        # 返回数据
        result = {
            "code": 1,
            "msg": "ok",
            "data":{
                "sum_money": sum_money,
                "all_select": is_select_all
            }
        }
        return JsonResponse(result)

class CartItemAPI(View):
    def post(self, req):
        # 用户
        user = req.user
        c_id = req.POST.get("c_id")

        # 确定购物车数据
        cart_item = Cart.objects.get(id=int(c_id))
        # 检查库存
        if cart_item.goods.storenums < 1:
            data = {
                "code": 2,
                "msg": "库存不足",
                "data": ""
            }
            return JsonResponse(data)

        # 给商品的数量在原来基础上加1
        cart_item.num += 1
        cart_item.save()

        # 算钱
        cart_items = Cart.objects.filter(
            user_id=user.id, is_selected=True
        )
        sum_money = get_cart_money(cart_items)

        # 返回数据
        data = {
            "code": 1,
            "msg": "ok",
            "data": {
                "num": cart_item.num,
                "sum_money": sum_money
            }
        }
        return JsonResponse(data)

    def delete(self, req):
        # 用户
        user = req.user

        # 购物车商品
        c_id = QueryDict(req.body).get("c_id")
        cart_item = Cart.objects.get(pk=int(c_id))

        # 减数量
        cart_item.num -= 1
        cart_item.save()

        # 判断是不是减到0
        if cart_item.num == 0:
            goods_num = 0
            cart_item.delete()
        else:
            goods_num = cart_item.num

        # 算钱
        cart_items = Cart.objects.filter(
            user=user,
            is_selected=True
        )
        sum_money = get_cart_money(cart_items)

        # 返回数据

        data = {
            "code": 1,
            "msg": "ok",
            "data": {
                "num": goods_num,
                "sum_money": sum_money
            }
        }
        return JsonResponse(data)

class OrderAPI(View):

    def get(self, req):
        user = req.user
        # 先获取购物车里的数据
        cart_items = Cart.objects.filter(
            user_id=user.id,
            is_selected=True
        )
        if not cart_items.exists():
            return render(req, "order/order_detail.html")
        # 创建order
        order = Order.objects.create(
            user=user
        )
        # 循环创建我们的订单数据
        for i in cart_items:
            OrderItem.objects.create(
                order=order,
                goods=i.goods,
                num=i.num,
                buy_money=i.goods.price
            )
        # 算钱
        sum_money = get_cart_money(cart_items)

        # 清空购物车内的商品
        cart_items.delete()
        data = {
            "sum_money": sum_money,
            "order": order
        }
        return render(req, "order/order_detail.html", data)
