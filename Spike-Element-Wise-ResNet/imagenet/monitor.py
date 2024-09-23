import torch
import numpy as np
from torch import nn
from typing import Callable, Any
from spikingjelly.cext import neuron
import threading
from torch.utils.tensorboard import SummaryWriter
import os
import time
import re
import datetime

def unpack_len1_tuple(x: tuple or torch.Tensor):
    if isinstance(x, tuple) and x.__len__() == 1:
        return x[0]
    else:
        return x



class BaseMonitor:
    def __init__(self):
        self.hooks = []
        self.monitored_layers = []
        self.records = []
        self.name_records_index = {}
        self._enable = True

    def __getitem__(self, i):
        if isinstance(i, int):
            return self.records[i]
        elif isinstance(i, str):
            y = []
            for index in self.name_records_index[i]:
                y.append(self.records[index])
            return y
        else:
            raise ValueError(i)

    def clear_recorded_data(self):
        self.records.clear()
        for k, v in self.name_records_index.items():
            v.clear()


    def enable(self):
        self._enable = True


    def disable(self):
        self._enable = False


    def is_enable(self):
        return self._enable


    def remove_hooks(self):
        for hook in self.hooks:
            hook.remove()


    def __del__(self):
        self.remove_hooks()


class GradOutputMonitor(BaseMonitor):
    def __init__(self, net: nn.Module, instance: Any or tuple = None, function_on_grad_output: Callable = lambda x: x):
        """
        * :ref:`API in English <GradOutputMonitor-en>`

        .. _GradOutputMonitor-cn:

        :param net: 一个神经网络
        :type net: nn.Module
        :param instance: 被监视的模块的数据类型。若为 ``None`` 则表示类型为 ``type(net)``
        :type instance: Any or tuple
        :param function_on_grad_output: 作用于被监控的模块输出的输出的的梯度的函数
        :type function_on_grad_output: Callable

        对 ``net`` 中所有类型为 ``instance`` 的模块的输出的梯度使用 ``function_on_grad_output`` 作用后，记录到类型为 `list`` 的 ``self.records`` 中。
        可以通过 ``self.enable()`` 和 ``self.disable()`` 来启用或停用这个监视器。
        可以通过 ``self.clear_recorded_data()`` 来清除已经记录的数据。

        阅读监视器的教程以获得更多信息。

        .. Note::

            对于一个模块，输入为 :math:`X`，输出为 :math:`Y`，损失为 :math:`L`，则 ``GradOutputMonitor`` 记录的是对输出的梯度 :math:`\\frac{\\partial L}{\\partial Y}`。

        示例代码：

        .. code-block:: python

            import torch
            import torch.nn as nn
            from spikingjelly.activation_based import monitor, neuron, functional, layer

            class Net(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.fc1 = layer.Linear(8, 4)
                    self.sn1 = neuron.IFNode()
                    self.fc2 = layer.Linear(4, 2)
                    self.sn2 = neuron.IFNode()
                    functional.set_step_mode(self, 'm')

                def forward(self, x_seq: torch.Tensor):
                    x_seq = self.fc1(x_seq)
                    x_seq = self.sn1(x_seq)
                    x_seq = self.fc2(x_seq)
                    x_seq = self.sn2(x_seq)
                    return x_seq

            net = Net()
            for param in net.parameters():
                param.data.abs_()

            mtor = monitor.GradOutputMonitor(net, instance=neuron.IFNode)

            net(torch.rand([1, 8])).sum().backward()
            print(f'mtor.records={mtor.records}')
            # mtor.records=[tensor([[1., 1.]]), tensor([[0.1372, 0.1081, 0.0880, 0.1089]])]
            print(f'mtor[0]={mtor[0]}')
            # mtor[0]=tensor([[1., 1.]])
            print(f'mtor.monitored_layers={mtor.monitored_layers}')
            # mtor.monitored_layers=['sn1', 'sn2']
            print(f"mtor['sn1']={mtor['sn1']}")
            # mtor['sn1']=[tensor([[0.1372, 0.1081, 0.0880, 0.1089]])]



        * :ref:`中文 API <GradOutputMonitor-cn>`

        .. _GradOutputMonitor-en:

        :param net: a network
        :type net: nn.Module
        :param instance: the instance of modules to be monitored. If ``None``, it will be regarded as ``type(net)``
        :type instance: Any or tuple
        :param function_on_grad_output: the function that applies on the grad of monitored modules' inputs
        :type function_on_grad_output: Callable

        Applies ``function_on_grad_output`` on grad of outputs of all modules whose instances are ``instance`` in ``net``, and records
        the data into ``self.records``, which is a ``list``.
        Call ``self.enable()`` or ``self.disable()`` to enable or disable the monitor.
        Call ``self.clear_recorded_data()`` to clear the recorded data.

        Refer to the tutorial about the monitor for more details.

        .. admonition:: Note
            :class: note

            Denote the input and output of the monitored module as :math:`X` and :math:`Y`, and the loss is :math:`L`, then ``GradOutputMonitor`` will record the gradient of output, which is :math:`\\frac{\\partial L}{\\partial Y}`.


        Codes example:

        .. code-block:: python

            import torch
            import torch.nn as nn
            from spikingjelly.activation_based import monitor, neuron, functional, layer

            class Net(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.fc1 = layer.Linear(8, 4)
                    self.sn1 = neuron.IFNode()
                    self.fc2 = layer.Linear(4, 2)
                    self.sn2 = neuron.IFNode()
                    functional.set_step_mode(self, 'm')

                def forward(self, x_seq: torch.Tensor):
                    x_seq = self.fc1(x_seq)
                    x_seq = self.sn1(x_seq)
                    x_seq = self.fc2(x_seq)
                    x_seq = self.sn2(x_seq)
                    return x_seq

            net = Net()
            for param in net.parameters():
                param.data.abs_()

            mtor = monitor.GradOutputMonitor(net, instance=neuron.IFNode)

            net(torch.rand([1, 8])).sum().backward()
            print(f'mtor.records={mtor.records}')
            # mtor.records=[tensor([[1., 1.]]), tensor([[0.1372, 0.1081, 0.0880, 0.1089]])]
            print(f'mtor[0]={mtor[0]}')
            # mtor[0]=tensor([[1., 1.]])
            print(f'mtor.monitored_layers={mtor.monitored_layers}')
            # mtor.monitored_layers=['sn1', 'sn2']
            print(f"mtor['sn1']={mtor['sn1']}")
            # mtor['sn1']=[tensor([[0.1372, 0.1081, 0.0880, 0.1089]])]

        """

        super().__init__()
        self.function_on_grad_output = function_on_grad_output
        if instance is None:
            instance = type(net)
        for name, m in net.named_modules():
            if isinstance(m, instance):
                self.monitored_layers.append(name)
                self.name_records_index[name] = []
                if torch.__version__ >= torch.torch_version.TorchVersion('1.8.0'):
                    self.hooks.append(m.register_full_backward_hook(self.create_hook(name)))
                else:
                    self.hooks.append(m.register_backward_hook(self.create_hook(name)))

    def create_hook(self, name):
        def hook(m, grad_input, grad_output):
            if self.is_enable():
                self.name_records_index[name].append(self.records.__len__())
                self.records.append(self.function_on_grad_output(unpack_len1_tuple(grad_output)))

        return hook

if __name__ == '__main__':
    import torch
    import torch.nn as nn
    from spikingjelly.clock_driven import neuron, functional, layer
    from sew_resnet import sew_resnet18

    model = sew_resnet18(zero_init_residual=False, connect_f="ADD").cuda()
    input = torch.randn((1,3,224,224)).cuda()

    net = model.layer4

    mtor = GradOutputMonitor(net, instance=nn.Conv2d)

    model(input).sum().backward()
    print(f'mtor.records={mtor.records}')


